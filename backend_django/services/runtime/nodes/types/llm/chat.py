from __future__ import annotations

from typing import Any, Optional

from base.handlers.langfuse_handler import (
    get_langfuse_metadata,
    langfuse_callback_handler,
)
from services.session_history import SESSION_ID_KEY
from services.runtime.json_utils import JSON_RESPONSE_INSTRUCTION, parse_json_content
from services.runtime.langfuse_tracing import (
    end_current_runtime_span,
    log_llm_generation,
    start_current_runtime_span,
)
from services.runtime.nodes.types.llm.common import (
    build_chat_messages as _build_chat_messages,
    build_langchain_chat_model,
    build_langchain_messages as _build_langchain_messages,
    build_trace_output_messages as _build_trace_output_messages,
    extract_langchain_content as _extract_langchain_content,
    render_template as _render_template,
    resolve_llm_settings,
    resolve_llm_system_prompt as _resolve_llm_system_prompt,
    validate_llm_settings,
)
from type_defs import ExecutionContext, JSONMapping, NodeRunner, StatePayload


def _apply_confidence_check(response, *, config: JSONMapping, node_name=None):
    """If confidence threshold is enabled and the LLM response confidence is below
    the threshold, call langgraph.types.interrupt() to pause the graph for human
    review.  Returns the (possibly human-overridden) response on resume."""
    if not config.get("confidence_threshold_enabled"):
        return response

    threshold = float(config.get("confidence_threshold") or 0.7)
    confidence_key = str(config.get("confidence_key") or "confidence").strip()

    confidence = None
    if isinstance(response, dict):
        raw = response.get(confidence_key)
        if raw is not None:
            try:
                confidence = float(raw)
            except (ValueError, TypeError):
                pass

    if confidence is None or confidence >= threshold:
        return response

    from langgraph.types import interrupt
    reason = (
        f"Node '{node_name}' responded with {confidence:.0%} confidence, "
        f"which is below the required threshold of {threshold:.0%}. "
        "Human review is required before the run can continue."
    )
    sla_timeout_seconds = config.get("sla_timeout_seconds")
    timeout_action = str(config.get("timeout_action") or "auto_approve")
    human_value = interrupt({
        "interrupt_type": "confidence_check",
        "node_name": node_name,
        "confidence": confidence,
        "threshold": threshold,
        "llm_response": response,
        "reason": reason,
        "sla_timeout_seconds": int(sla_timeout_seconds) if sla_timeout_seconds else None,
        "timeout_action": timeout_action,
    })
    return human_value


def build_chat_llm_node(
    config: JSONMapping,
    *,
    execution_context: Optional[ExecutionContext] = None,
    agent_name: Optional[str] = None,
    run_id: Optional[str] = None,
    node_name: Optional[str] = None,
    session_id: Optional[str] = None,
) -> NodeRunner:
    def llm_node(state: StatePayload) -> StatePayload:
        settings = resolve_llm_settings(config)
        model_span = None
        model_scope = None
        model_span_output: dict[str, Any] | None = None
        system_prompt, prompt_metadata = _resolve_llm_system_prompt(config, state)
        if settings.parse_json:
            system_prompt = f"{system_prompt.rstrip()}\n\n{JSON_RESPONSE_INSTRUCTION}"
        user_prompt = _render_template(settings.user_prompt_template, state)
        messages = _build_chat_messages(system_prompt, user_prompt, state)

        error_msg = validate_llm_settings(settings)
        if error_msg:
            log_llm_generation(
                name="llm_call",
                provider=settings.provider,
                model=settings.model_name,
                input_payload=messages,
                error=error_msg,
            )
            return {**state, "_error": error_msg, settings.output_key: None}

        try:
            model_span, model_scope = start_current_runtime_span(
                name="model",
                input_payload=messages,
                metadata={
                    "node_name": node_name,
                    "provider": settings.provider,
                    "model": settings.model_name,
                    "llm_runtime": "chat_model",
                },
            )
            langfuse_session_id = str(state.get(SESSION_ID_KEY) or session_id or "").strip() or None
            shared_langfuse_handler = (execution_context or {}).get("langfuse_handler")
            shared_langfuse_metadata = dict((execution_context or {}).get("langfuse_metadata") or {})
            langfuse_handler = shared_langfuse_handler or langfuse_callback_handler()
            langfuse_metadata = {
                **shared_langfuse_metadata,
                **get_langfuse_metadata(
                    session_id=langfuse_session_id,
                    tags=[value for value in (agent_name, node_name, settings.provider) if value],
                    node_name=node_name,
                    output_key=settings.output_key,
                    prompt_name=prompt_metadata.get("prompt_name"),
                    prompt_source=prompt_metadata.get("prompt_source"),
                    prompt_label=prompt_metadata.get("prompt_label"),
                    llm_runtime="chat_model",
                ),
            }
            callbacks = [langfuse_handler] if langfuse_handler is not None else []

            if settings.provider in ("azure_openai", "azure", "openai"):
                try:
                    llm = build_langchain_chat_model(
                        settings,
                        enable_native_json_mode=settings.parse_json,
                    )
                    response = llm.invoke(
                        _build_langchain_messages(messages),
                        config={"callbacks": callbacks, "metadata": langfuse_metadata},
                    )
                    content = _extract_langchain_content(response)
                except Exception:
                    import openai

                    client = openai.AzureOpenAI(
                        api_key=settings.api_key,
                        azure_endpoint=settings.azure_endpoint,
                        api_version=settings.azure_api_version,
                    )
                    completion_kwargs = {
                        "model": settings.azure_deployment,
                        "messages": messages,
                        "temperature": settings.temperature,
                        "max_tokens": settings.max_tokens,
                    }
                    if settings.parse_json:
                        completion_kwargs["response_format"] = {"type": "json_object"}
                    response = client.chat.completions.create(**completion_kwargs)
                    content = response.choices[0].message.content
                    log_llm_generation(
                        name=node_name or "llm_call",
                        provider=settings.provider,
                        model=settings.azure_deployment,
                        input_payload=messages,
                        output_payload=_build_trace_output_messages(content),
                        metadata={
                            "output_key": settings.output_key,
                            "llm_runtime": "chat_model",
                            **prompt_metadata,
                        },
                    )

            elif settings.provider == "anthropic":
                try:
                    llm = build_langchain_chat_model(settings)
                    response = llm.invoke(
                        _build_langchain_messages(messages),
                        config={"callbacks": callbacks, "metadata": langfuse_metadata},
                    )
                    content = _extract_langchain_content(response)
                except Exception:
                    import anthropic

                    client = anthropic.Anthropic(api_key=settings.api_key)
                    response = client.messages.create(
                        model=settings.model_name,
                        max_tokens=settings.max_tokens,
                        system=system_prompt,
                        messages=[
                            message
                            for message in messages
                            if message["role"] in {"user", "assistant"}
                        ],
                    )
                    content = response.content[0].text
                    log_llm_generation(
                        name=node_name or "llm_call",
                        provider=settings.provider,
                        model=settings.model_name,
                        input_payload=messages,
                        output_payload=_build_trace_output_messages(content),
                        metadata={
                            "output_key": settings.output_key,
                            "llm_runtime": "chat_model",
                            **prompt_metadata,
                        },
                    )

            else:
                content = f"[Unsupported provider: {settings.provider}]"

            if settings.provider not in ("azure_openai", "azure", "openai", "anthropic"):
                log_llm_generation(
                    name=node_name or "llm_call",
                    provider=settings.provider,
                    model=settings.model_name,
                    input_payload=messages,
                    output_payload=_build_trace_output_messages(content),
                    metadata={
                        "output_key": settings.output_key,
                        "llm_runtime": "chat_model",
                        **prompt_metadata,
                    },
                )

            if settings.parse_json:
                content = parse_json_content(content)

            content = _apply_confidence_check(content, config=config, node_name=node_name)

            model_span_output = {
                "output_key": settings.output_key,
                "status": "success",
            }
            return {**state, settings.output_key: content}

        except Exception as exc:
            model_span_output = {
                "output_key": settings.output_key,
                "status": "error",
                "error": str(exc),
            }
            log_llm_generation(
                name=node_name or "llm_call",
                provider=settings.provider,
                model=(
                    settings.azure_deployment
                    if settings.provider in ("azure_openai", "azure", "openai")
                    else settings.model_name
                ),
                input_payload=messages,
                error=str(exc),
                metadata={
                    "output_key": settings.output_key,
                    "llm_runtime": "chat_model",
                    **prompt_metadata,
                },
            )
            return {**state, "_error": str(exc), settings.output_key: None}
        finally:
            end_current_runtime_span(
                model_span,
                model_scope,
                output_payload=model_span_output,
            )

    return llm_node
