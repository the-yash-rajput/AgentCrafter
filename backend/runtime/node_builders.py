import os
import json
from typing import Any, Callable, Optional
from jinja2 import Template

from base.handlers.langfuse_handler import (
    get_langfuse_metadata,
    langfuse_callback_handler,
)
from base.utilities.langchain_agent_prompt_utilities import get_prompt_with_env
from runtime.json_utils import JSON_RESPONSE_INSTRUCTION, parse_json_content
from runtime.langfuse_tracing import log_llm_generation
from task_runner import PythonTaskConfig, PythonTaskRunner

# ─── Node Builders ────────────────────────────────────────────────────────────

def build_functional_node(
    config: dict,
    *,
    db=None,
    current_agent_id: Optional[int] = None,
    execution_context: Optional[dict] = None,
) -> Callable:
    """Build a functional node from config."""
    function_type = config.get("function_type", "python_inline")

    if function_type == "python_inline":
        inline_config = config.get("python_inline", {})
        code = inline_config.get("code", "def run(state):\n    return state")
        task_runner = PythonTaskRunner()
        task_config = PythonTaskConfig.from_inline_config(inline_config)

        def functional_node(state: dict) -> dict:
            try:
                result = task_runner.run(code=code, state=state, config=task_config)
                return result.output
            except Exception as e:
                return {**state, "_error": str(e)}

        return functional_node

    elif function_type == "api_call":
        api_cfg = config.get("api_call", {})
        
        def api_node(state: dict) -> dict:
            url_template = Template(api_cfg.get("url", ""))
            url = url_template.render(**state)
            method = api_cfg.get("method", "GET").upper()
            headers = api_cfg.get("headers", {})
            body_template_str = api_cfg.get("body_template", "")
            output_key = api_cfg.get("output_key", "api_result")

            body = None
            if body_template_str:
                body = Template(body_template_str).render(**state)
                try:
                    body = json.loads(body)
                except Exception:
                    pass

            try:
                import httpx

                with httpx.Client() as client:
                    response = client.request(method, url, headers=headers, json=body)
                    response.raise_for_status()
                    return {**state, output_key: response.json()}
            except Exception as e:
                return {**state, "_error": str(e)}

        return api_node

    elif function_type == "data_transform":
        operations = config.get("data_transform", {}).get("operations", [])
        
        def transform_node(state: dict) -> dict:
            result = dict(state)
            for op in operations:
                op_type = op.get("type")
                op_config = op.get("config", {})
                if op_type == "extract":
                    key = op_config.get("key")
                    new_key = op_config.get("new_key", key)
                    if key and key in result:
                        result[new_key] = result[key]
                elif op_type == "merge":
                    result.update(op_config.get("data", {}))
            return result

        return transform_node

    elif function_type == "agent_call":
        agent_cfg = config.get("agent_call", {})

        def agent_call_node(state: dict) -> dict:
            target_agent_id = agent_cfg.get("target_agent_id")
            target_agent_name = str(agent_cfg.get("target_agent_name") or "").strip()
            input_mode = agent_cfg.get("input_mode", "entire_state")
            input_key = str(agent_cfg.get("input_key") or "").strip()
            input_template = str(agent_cfg.get("input_template") or "").strip()
            output_mode = agent_cfg.get("output_mode", "merge_state")
            output_key = str(agent_cfg.get("output_key") or "agent_result").strip() or "agent_result"
            include_run_metadata = bool(agent_cfg.get("include_run_metadata", False))

            if db is None:
                return {**state, "_error": "Agent Call nodes require a database session"}

            from models import Agent
            from runtime.graph_runner import GraphRunner

            target_agent = None
            if target_agent_id not in (None, ""):
                try:
                    target_agent = db.query(Agent).filter(Agent.id == int(target_agent_id)).first()
                except (TypeError, ValueError):
                    return {**state, "_error": f"Invalid target agent ID '{target_agent_id}'"}
            elif target_agent_name:
                target_agent = db.query(Agent).filter(Agent.name == target_agent_name).first()
            else:
                return {**state, "_error": "Agent Call node requires target_agent_id or target_agent_name"}

            if not target_agent:
                target_label = target_agent_name or target_agent_id
                return {**state, "_error": f"Target agent '{target_label}' not found"}

            if current_agent_id is not None and target_agent.id == current_agent_id:
                return {**state, "_error": "Agent Call node cannot target the same agent"}

            nested_input: Any
            if input_mode == "state_key":
                if not input_key:
                    return {**state, "_error": "Agent Call node requires input_key for state_key mode"}
                nested_input = state.get(input_key, {})
            elif input_mode == "template":
                if not input_template:
                    return {**state, "_error": "Agent Call node requires input_template for template mode"}
                try:
                    rendered = Template(input_template).render(**state)
                    nested_input = json.loads(rendered)
                except Exception as e:
                    return {**state, "_error": f"Failed to render agent input template: {e}"}
            else:
                nested_input = dict(state)

            if not isinstance(nested_input, dict):
                return {**state, "_error": "Agent Call node input must resolve to a JSON object"}

            try:
                result = GraphRunner(db).compile_and_run(
                    target_agent.id,
                    nested_input,
                    execution_context=execution_context,
                )
            except Exception as e:
                return {**state, "_error": str(e)}

            child_output = result.get("output", {})
            if not isinstance(child_output, dict):
                child_output = {output_key: child_output}

            next_state: dict[str, Any]
            if output_mode == "write_to_key":
                next_state = {**state, output_key: child_output}
            else:
                next_state = child_output

            if include_run_metadata:
                next_state = {
                    **next_state,
                    f"{output_key}_meta": {
                        "target_agent_id": target_agent.id,
                        "target_agent_name": target_agent.name,
                        "run_id": result.get("run_id"),
                        "status": result.get("status"),
                    },
                }

            return next_state

        return agent_call_node

    # Default passthrough
    def passthrough(state: dict) -> dict:
        return state
    return passthrough


def _render_template(template_value: Any, state: dict) -> str:
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


def _resolve_llm_system_prompt(config: dict, state: dict) -> tuple[str, dict]:
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


def build_llm_node(
    config: dict,
    *,
    agent_name: Optional[str] = None,
    run_id: Optional[str] = None,
    node_name: Optional[str] = None,
) -> Callable:
    """Build an LLM call node from config."""
    provider = str(config.get("provider", "azure_openai")).strip().lower()
    model = config.get("model", "ai-agent-4o")
    provider_key_env_map = {
        "azure_openai": "AZURE_OPENAI_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
        # Backward-compatible alias: existing saved "openai" nodes now run via Azure OpenAI.
        "openai": "AZURE_OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    api_key_env = config.get("api_key_env_var") or provider_key_env_map.get(provider, "AZURE_OPENAI_API_KEY")
    user_prompt_template = config.get("user_prompt_template", "{{input}}")
    temperature = config.get("temperature", 0.7)
    max_tokens = config.get("max_tokens", 1000)
    output_key = config.get("output_key", "llm_response")
    parse_json = config.get("parse_json_response", False)

    def llm_node(state: dict) -> dict:
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
            return {
                **state,
                "_error": error_msg,
                output_key: None,
            }
        if provider in ("azure_openai", "azure", "openai") and not azure_endpoint:
            error_msg = "Missing Azure endpoint. Set AZURE_OPENAI_ENDPOINT in backend runtime."
            log_llm_generation(
                name="llm_call",
                provider=provider,
                model=model_name,
                input_payload={"messages": messages},
                error=error_msg,
            )
            return {
                **state,
                "_error": error_msg,
                output_key: None,
            }
        if provider in ("azure_openai", "azure", "openai") and not azure_deployment:
            error_msg = "Missing Azure deployment name. Set node model or azure_deployment."
            log_llm_generation(
                name="llm_call",
                provider=provider,
                model=model_name,
                input_payload={"messages": messages},
                error=error_msg,
            )
            return {
                **state,
                "_error": error_msg,
                output_key: None,
            }

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

                    llm = AzureChatOpenAI(
                        **llm_kwargs,
                    )
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

        except Exception as e:
            log_llm_generation(
                name=node_name or "llm_call",
                provider=provider,
                model=azure_deployment if provider in ("azure_openai", "azure", "openai") else model_name,
                input_payload={"messages": messages},
                error=str(e),
                metadata={
                    "output_key": output_key,
                    **prompt_metadata,
                },
            )
            return {**state, "_error": str(e), output_key: None}

    return llm_node


# ─── Condition Router Builder ─────────────────────────────────────────────────

def build_condition_router(condition_config: dict, edges: list) -> Callable:
    """Build a routing function for conditional edges."""
    condition_type = condition_config.get("condition_type", "state_key_equals")

    def router(state: dict) -> str:
        if condition_type == "state_key_equals":
            cfg = condition_config.get("state_key_equals", {})
            key = cfg.get("key", "")
            value = cfg.get("value", "")
            state_val = state.get(key, "")
            # Find matching edge target
            for edge in edges:
                if edge.get("label") == str(state_val) or edge.get("target") == str(state_val):
                    return edge.get("target")
            # Default to first edge target
            return edges[0].get("target") if edges else "__end__"

        elif condition_type == "python_expression":
            cfg = condition_config.get("python_expression", {})
            expression = cfg.get("expression", "True")
            try:
                result = eval(expression, {"state": state})
                if result and len(edges) > 0:
                    return edges[0].get("target")
                elif not result and len(edges) > 1:
                    return edges[1].get("target")
            except Exception:
                pass
            return edges[0].get("target") if edges else "__end__"

        elif condition_type == "llm_router":
            cfg = condition_config.get("llm_router", {})
            routing_key = cfg.get("routing_key", "next_step")
            routing_value = state.get(routing_key, "")
            for edge in edges:
                if edge.get("label") == str(routing_value):
                    return edge.get("target")
            return edges[0].get("target") if edges else "__end__"

        return edges[0].get("target") if edges else "__end__"

    return router
