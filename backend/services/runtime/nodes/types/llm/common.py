from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from jinja2 import Template

from base.utilities.langchain_agent_prompt_utilities import get_prompt_with_env
from services.session_history import CONVERSATION_HISTORY_KEY, normalize_conversation_history
from type_defs import JSONMapping, StatePayload


@dataclass(slots=True)
class ResolvedLLMSettings:
    provider: str
    model_name: str
    resolved_api_key_env: str
    api_key: str
    azure_endpoint: str
    azure_api_version: str
    azure_deployment: str
    user_prompt_template: str
    temperature: Any
    max_tokens: Any
    output_key: str
    parse_json: bool


def render_template(template_value: Any, state: StatePayload) -> str:
    template_text = str(template_value or "")
    try:
        return Template(template_text).render(**state)
    except Exception:
        return template_text


def extract_langchain_content(response: Any) -> Any:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    chunks.append(item["text"])
                else:
                    chunks.append(json.dumps(item))
            else:
                chunks.append(str(item))
        return "\n".join(chunk for chunk in chunks if chunk)
    return content


def build_trace_output_messages(content: Any) -> list[dict[str, str]] | None:
    normalized_messages = normalize_conversation_history(content)
    if normalized_messages:
        return normalized_messages

    if content is None:
        return None

    if isinstance(content, str):
        serialized_content = content.strip()
    else:
        serialized_content = json.dumps(content, ensure_ascii=True, default=str)

    if not serialized_content:
        return None

    return [{"role": "assistant", "content": serialized_content}]


def build_chat_messages(system_prompt: str, user_prompt: str, state: StatePayload) -> list[dict[str, str]]:
    history_messages = normalize_conversation_history(state.get(CONVERSATION_HISTORY_KEY))
    return [
        {"role": "system", "content": system_prompt},
        *history_messages,
        {"role": "user", "content": user_prompt},
    ]


def build_agent_messages(user_prompt: str, state: StatePayload) -> list[dict[str, str]]:
    history_messages = normalize_conversation_history(state.get(CONVERSATION_HISTORY_KEY))
    return [
        *history_messages,
        {"role": "user", "content": user_prompt},
    ]


def build_langchain_messages(messages: list[dict[str, str]]) -> list[Any]:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    langchain_messages: list[Any] = []
    for message in messages:
        role = message["role"]
        content = message["content"]
        if role == "system":
            langchain_messages.append(SystemMessage(content=content))
        elif role == "assistant":
            langchain_messages.append(AIMessage(content=content))
        else:
            langchain_messages.append(HumanMessage(content=content))

    return langchain_messages


def resolve_llm_system_prompt(config: JSONMapping, state: StatePayload) -> tuple[str, JSONMapping]:
    fallback_prompt = config.get("system_prompt", "You are a helpful assistant.")
    prompt_name = str(config.get("langfuse_prompt_name") or "").strip()
    use_langfuse_prompt = bool(config.get("use_langfuse_prompt")) and bool(prompt_name)

    if not use_langfuse_prompt:
        return render_template(fallback_prompt, state), {
            "prompt_source": "inline",
            "prompt_name": None,
            "prompt_label": None,
        }

    prompt_object = get_prompt_with_env(prompt_name, fallback_content=fallback_prompt)
    prompt_content = str(getattr(prompt_object, "content", "") or "").strip()
    prompt_source = getattr(prompt_object, "source", "inline") if prompt_object else "inline"
    prompt_label = getattr(prompt_object, "label", None) if prompt_object else None

    if prompt_source == "langfuse" and prompt_content:
        return render_template(prompt_content, state), {
            "prompt_source": "langfuse",
            "prompt_name": prompt_name,
            "prompt_label": prompt_label,
        }

    return render_template(fallback_prompt, state), {
        "prompt_source": "inline",
        "prompt_name": None,
        "prompt_label": None,
    }


def resolve_llm_settings(config: JSONMapping) -> ResolvedLLMSettings:
    provider = str(config.get("provider", "azure_openai")).strip().lower()
    model = config.get("model", "ai-agent-4o")
    provider_key_env_map = {
        "azure_openai": "AZURE_OPENAI_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
        "openai": "AZURE_OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    api_key_env = config.get("api_key_env_var") or provider_key_env_map.get(provider, "AZURE_OPENAI_API_KEY")
    resolved_api_key_env = str(api_key_env or "").strip() or provider_key_env_map.get(provider, "AZURE_OPENAI_API_KEY")
    api_key = os.getenv(resolved_api_key_env, "").strip()
    if provider in ("azure_openai", "azure", "openai") and not api_key and resolved_api_key_env == "OPENAI_API_KEY":
        resolved_api_key_env = "AZURE_OPENAI_API_KEY"
        api_key = os.getenv(resolved_api_key_env, "").strip()

    model_name = str(model or "").strip()
    azure_endpoint = str(
        config.get("azure_endpoint") or os.getenv("AZURE_OPENAI_ENDPOINT", "")
    ).strip()
    azure_api_version = str(
        config.get("azure_api_version") or os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    ).strip()
    azure_deployment = str(config.get("azure_deployment") or model_name).strip()

    return ResolvedLLMSettings(
        provider=provider,
        model_name=model_name,
        resolved_api_key_env=resolved_api_key_env,
        api_key=api_key,
        azure_endpoint=azure_endpoint,
        azure_api_version=azure_api_version,
        azure_deployment=azure_deployment,
        user_prompt_template=config.get("user_prompt_template", "{{input}}"),
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 1000),
        output_key=config.get("output_key", "llm_response"),
        parse_json=bool(config.get("parse_json_response", False)),
    )


def validate_llm_settings(settings: ResolvedLLMSettings) -> str | None:
    if settings.provider in ("azure_openai", "azure", "openai", "anthropic") and not settings.api_key:
        return (
            f"Missing API key for provider '{settings.provider}'. "
            f"Set environment variable '{settings.resolved_api_key_env}' in backend runtime."
        )

    if settings.provider in ("azure_openai", "azure", "openai") and not settings.azure_endpoint:
        return "Missing Azure endpoint. Set AZURE_OPENAI_ENDPOINT in backend runtime."

    if settings.provider in ("azure_openai", "azure", "openai") and not settings.azure_deployment:
        return "Missing Azure deployment name. Set node model or azure_deployment."

    return None


def build_langchain_chat_model(
    settings: ResolvedLLMSettings,
    *,
    enable_native_json_mode: bool = False,
):
    if settings.provider in ("azure_openai", "azure", "openai"):
        from langchain_openai import AzureChatOpenAI

        llm_kwargs = {
            "azure_deployment": settings.azure_deployment,
            "api_key": settings.api_key,
            "azure_endpoint": settings.azure_endpoint,
            "api_version": settings.azure_api_version,
            "model": settings.model_name or settings.azure_deployment,
            "temperature": settings.temperature,
            "max_tokens": settings.max_tokens,
        }
        if enable_native_json_mode:
            llm_kwargs["model_kwargs"] = {
                "response_format": {"type": "json_object"}
            }

        return AzureChatOpenAI(**llm_kwargs)

    if settings.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            api_key=settings.api_key,
            model=settings.model_name,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        )

    raise ValueError(f"Unsupported provider '{settings.provider}' for LangChain chat model")


def extract_agent_result_content(result: Any) -> tuple[Any, Any]:
    if not isinstance(result, dict):
        return extract_langchain_content(result), None

    structured_response = result.get("structured_response")
    messages = normalize_conversation_history(result.get("messages"))
    for message in reversed(messages):
        if message["role"] == "assistant":
            return message["content"], structured_response

    if isinstance(structured_response, dict) and structured_response.get("final_answer"):
        return structured_response.get("final_answer"), structured_response

    return None, structured_response
