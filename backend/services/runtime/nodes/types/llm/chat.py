from __future__ import annotations

import json
import os
from typing import Any, Optional

from jinja2 import Template

from base.handlers.langfuse_handler import (
    get_langfuse_metadata,
    langfuse_callback_handler,
)
from base.utilities.langchain_agent_prompt_utilities import get_prompt_with_env
from backend.services.runtime.json_utils import JSON_RESPONSE_INSTRUCTION, parse_json_content
from backend.services.runtime.langfuse_tracing import log_llm_generation
from type_defs import JSONMapping, NodeRunner, StatePayload


def _render_template(template_value: Any, state: StatePayload) -> str:
    template_text = str(template_value or "")
    try:
        return Template(template_text).render(**state)
    except Exception:
        return template_text


def _extract_langchain_content(response: Any) -> Any:
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


def _resolve_llm_system_prompt(config: JSONMapping, state: StatePayload) -> tuple[str, JSONMapping]:
    fallback_prompt = config.get("system_prompt", "You are a helpful assistant.")
    prompt_name = str(config.get("langfuse_prompt_name") or "").strip()
    use_langfuse_prompt = bool(config.get("use_langfuse_prompt")) and bool(prompt_name)

    if not use_langfuse_prompt:
        return _render_template(fallback_prompt, state), {
            "prompt_source": "inline",
            "prompt_name": None,
            "prompt_label": None,
        }

    prompt_object = get_prompt_with_env(prompt_name, fallback_content=fallback_prompt)
    prompt_content = str(getattr(prompt_object, "content", "") or "").strip()
    prompt_source = getattr(prompt_object, "source", "inline") if prompt_object else "inline"
    prompt_label = getattr(prompt_object, "label", None) if prompt_object else None

    if prompt_source == "langfuse" and prompt_content:
        return _render_template(prompt_content, state), {
            "prompt_source": "langfuse",
            "prompt_name": prompt_name,
            "prompt_label": prompt_label,
        }

    return _render_template(fallback_prompt, state), {
        "prompt_source": "inline",
        "prompt_name": None,
        "prompt_label": None,
    }


def build_chat_llm_node(
    config: JSONMapping,
    *,
    agent_name: Optional[str] = None,
    run_id: Optional[str] = None,
    node_name: Optional[str] = None,
) -> NodeRunner:
    provider = str(config.get("provider", "azure_openai")).strip().lower()
    model = config.get("model", "ai-agent-4o")
    provider_key_env_map = {
        "azure_openai": "AZURE_OPENAI_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
        "openai": "AZURE_OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    api_key_env = config.get("api_key_env_var") or provider_key_env_map.get(provider, "AZURE_OPENAI_API_KEY")
    user_prompt_template = config.get("user_prompt_template", "{{input}}")
    temperature = config.get("temperature", 0.7)
    max_tokens = config.get("max_tokens", 1000)
    output_key = config.get("output_key", "llm_response")
    parse_json = config.get("parse_json_response", False)

    def llm_node(state: StatePayload) -> StatePayload:
        resolved_api_key_env = api_key_env
        api_key = os.getenv(api_key_env, "").strip()
        if provider in ("azure_openai", "azure", "openai") and not api_key and api_key_env == "OPENAI_API_KEY":
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

        system_prompt, prompt_metadata = _resolve_llm_system_prompt(config, state)
        if parse_json:
            system_prompt = f"{system_prompt.rstrip()}\n\n{JSON_RESPONSE_INSTRUCTION}"
        user_prompt = _render_template(user_prompt_template, state)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        if provider in ("azure_openai", "azure", "openai", "anthropic") and not api_key:
            error_msg = (
                f"Missing API key for provider '{provider}'. "
                f"Set environment variable '{resolved_api_key_env}' in backend runtime."
            )
            log_llm_generation(
                name="llm_call",
                provider=provider,
                model=model_name,
                input_payload={"messages": messages},
                error=error_msg,
            )
            return {**state, "_error": error_msg, output_key: None}

        if provider in ("azure_openai", "azure", "openai") and not azure_endpoint:
            error_msg = "Missing Azure endpoint. Set AZURE_OPENAI_ENDPOINT in backend runtime."
            log_llm_generation(
                name="llm_call",
                provider=provider,
                model=model_name,
                input_payload={"messages": messages},
                error=error_msg,
            )
            return {**state, "_error": error_msg, output_key: None}

        if provider in ("azure_openai", "azure", "openai") and not azure_deployment:
            error_msg = "Missing Azure deployment name. Set node model or azure_deployment."
            log_llm_generation(
                name="llm_call",
                provider=provider,
                model=model_name,
                input_payload={"messages": messages},
                error=error_msg,
            )
            return {**state, "_error": error_msg, output_key: None}

        try:
            langfuse_handler = langfuse_callback_handler()
            langfuse_metadata = get_langfuse_metadata(
                session_id=run_id,
                tags=[value for value in (agent_name, node_name, provider) if value],
                node_name=node_name,
                output_key=output_key,
                prompt_name=prompt_metadata.get("prompt_name"),
                prompt_source=prompt_metadata.get("prompt_source"),
                prompt_label=prompt_metadata.get("prompt_label"),
            )
            callbacks = [langfuse_handler] if langfuse_handler is not None else []

            if provider in ("azure_openai", "azure", "openai"):
                try:
                    from langchain_core.messages import HumanMessage, SystemMessage
                    from langchain_openai import AzureChatOpenAI

                    llm_kwargs = {
                        "azure_deployment": azure_deployment,
                        "api_key": api_key,
                        "azure_endpoint": azure_endpoint,
                        "api_version": azure_api_version,
                        "model": model_name or azure_deployment,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                    if parse_json:
                        llm_kwargs["model_kwargs"] = {
                            "response_format": {"type": "json_object"}
                        }

                    llm = AzureChatOpenAI(**llm_kwargs)
                    response = llm.invoke(
                        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
                        config={"callbacks": callbacks, "metadata": langfuse_metadata},
                    )
                    content = _extract_langchain_content(response)
                except Exception:
                    import openai

                    client = openai.AzureOpenAI(
                        api_key=api_key,
                        azure_endpoint=azure_endpoint,
                        api_version=azure_api_version,
                    )
                    completion_kwargs = {
                        "model": azure_deployment,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                    if parse_json:
                        completion_kwargs["response_format"] = {"type": "json_object"}
                    response = client.chat.completions.create(**completion_kwargs)
                    content = response.choices[0].message.content
                    log_llm_generation(
                        name=node_name or "llm_call",
                        provider=provider,
                        model=azure_deployment,
                        input_payload={"messages": messages},
                        output_payload=content,
                        metadata={
                            "output_key": output_key,
                            **prompt_metadata,
                        },
                    )

            elif provider == "anthropic":
                try:
                    from langchain_anthropic import ChatAnthropic
                    from langchain_core.messages import HumanMessage, SystemMessage

                    llm = ChatAnthropic(
                        api_key=api_key,
                        model=model_name,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    response = llm.invoke(
                        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
                        config={"callbacks": callbacks, "metadata": langfuse_metadata},
                    )
                    content = _extract_langchain_content(response)
                except Exception:
                    import anthropic

                    client = anthropic.Anthropic(api_key=api_key)
                    response = client.messages.create(
                        model=model,
                        max_tokens=max_tokens,
                        system=system_prompt,
                        messages=[{"role": "user", "content": user_prompt}],
                    )
                    content = response.content[0].text
                    log_llm_generation(
                        name=node_name or "llm_call",
                        provider=provider,
                        model=model_name,
                        input_payload={"messages": messages},
                        output_payload=content,
                        metadata={
                            "output_key": output_key,
                            **prompt_metadata,
                        },
                    )

            else:
                content = f"[Unsupported provider: {provider}]"

            if provider not in ("azure_openai", "azure", "openai", "anthropic"):
                log_llm_generation(
                    name=node_name or "llm_call",
                    provider=provider,
                    model=model_name,
                    input_payload={"messages": messages},
                    output_payload=content,
                    metadata={
                        "output_key": output_key,
                        **prompt_metadata,
                    },
                )

            if parse_json:
                content = parse_json_content(content)

            return {**state, output_key: content}

        except Exception as exc:
            log_llm_generation(
                name=node_name or "llm_call",
                provider=provider,
                model=azure_deployment if provider in ("azure_openai", "azure", "openai") else model_name,
                input_payload={"messages": messages},
                error=str(exc),
                metadata={
                    "output_key": output_key,
                    **prompt_metadata,
                },
            )
            return {**state, "_error": str(exc), output_key: None}

    return llm_node
