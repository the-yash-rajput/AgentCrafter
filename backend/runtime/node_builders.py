import os
import json
import asyncio
import httpx
from typing import Any, Dict, Callable, TypedDict
from jinja2 import Template
from datetime import datetime
from runtime.langfuse_tracing import log_llm_generation

# ─── Node Builders ────────────────────────────────────────────────────────────

def build_functional_node(config: dict) -> Callable:
    """Build a functional node from config."""
    function_type = config.get("function_type", "python_inline")

    if function_type == "python_inline":
        code = config.get("python_inline", {}).get("code", "def run(state): return state")
        
        def functional_node(state: dict) -> dict:
            local_ns = {}
            try:
                exec(code, {"__builtins__": __builtins__}, local_ns)
                if "run" in local_ns:
                    result = local_ns["run"](state)
                    if isinstance(result, dict):
                        return result
            except Exception as e:
                return {**state, "_error": str(e)}
            return state
        
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

    # Default passthrough
    def passthrough(state: dict) -> dict:
        return state
    return passthrough


def build_llm_node(config: dict) -> Callable:
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
    system_prompt = config.get("system_prompt", "You are a helpful assistant.")
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

        # Render prompt template
        try:
            user_prompt = Template(user_prompt_template).render(**state)
        except Exception:
            user_prompt = user_prompt_template

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
            if provider in ("azure_openai", "azure", "openai"):
                import openai
                client = openai.AzureOpenAI(
                    api_key=api_key,
                    azure_endpoint=azure_endpoint,
                    api_version=azure_api_version,
                )
                response = client.chat.completions.create(
                    model=azure_deployment,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content

            elif provider == "anthropic":
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                response = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                content = response.content[0].text

            else:
                content = f"[Unsupported provider: {provider}]"

            log_llm_generation(
                name="llm_call",
                provider=provider,
                model=azure_deployment if provider in ("azure_openai", "azure", "openai") else model_name,
                input_payload={"messages": messages},
                output_payload=content,
                metadata={"output_key": output_key},
            )

            if parse_json:
                try:
                    content = json.loads(content)
                except Exception:
                    pass

            return {**state, output_key: content}

        except Exception as e:
            log_llm_generation(
                name="llm_call",
                provider=provider,
                model=azure_deployment if provider in ("azure_openai", "azure", "openai") else model_name,
                input_payload={"messages": messages},
                error=str(e),
                metadata={"output_key": output_key},
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
