from __future__ import annotations

import os
from typing import Optional

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
    build_agent_messages,
    build_langchain_chat_model,
    build_langchain_messages,
    extract_agent_result_content,
    resolve_llm_settings,
    resolve_llm_system_prompt,
    render_template,
    validate_llm_settings,
)
from type_defs import ExecutionContext, JSONMapping, NodeRunner, StatePayload


def build_agent_llm_node(
    config: JSONMapping,
    *,
    execution_context: Optional[ExecutionContext] = None,
    agent_name: Optional[str] = None,
    run_id: Optional[str] = None,
    node_name: Optional[str] = None,
) -> NodeRunner:
    requested_provider = str(config.get("provider", "azure_openai")).strip().lower()
    if requested_provider not in {"azure_openai", "azure", "openai", "anthropic"}:
        from services.runtime.nodes.types.llm.chat import build_chat_llm_node

        return build_chat_llm_node(
            config,
            execution_context=execution_context,
            agent_name=agent_name,
            run_id=run_id,
            node_name=node_name,
        )

    try:
        from langchain.agents import create_agent  # noqa: F401

        from services.runtime.nodes.types.llm.middleware import build_agent_middlewares  # noqa: F401
    except Exception:
        from services.runtime.nodes.types.llm.chat import build_chat_llm_node

        return build_chat_llm_node(
            config,
            execution_context=execution_context,
            agent_name=agent_name,
            run_id=run_id,
            node_name=node_name,
        )

    def agent_llm_node(state: StatePayload) -> StatePayload:
        settings = resolve_llm_settings(config)
        system_prompt, prompt_metadata = resolve_llm_system_prompt(config, state)
        if settings.parse_json:
            system_prompt = f"{system_prompt.rstrip()}\n\n{JSON_RESPONSE_INSTRUCTION}"
        user_prompt = render_template(settings.user_prompt_template, state)
        input_messages = build_agent_messages(user_prompt, state)

        error_msg = validate_llm_settings(settings)
        if error_msg:
            log_llm_generation(
                name="llm_agent",
                provider=settings.provider,
                model=settings.model_name,
                input_payload=input_messages,
                error=error_msg,
            )
            return {**state, "_error": error_msg, settings.output_key: None}

        agent_span = None
        agent_scope = None
        agent_span_output: dict | None = None

        try:
            from langchain.agents import create_agent

            from services.runtime.nodes.types.llm.middleware import build_agent_middlewares

            agent_span, agent_scope = start_current_runtime_span(
                name="model",
                input_payload=input_messages,
                metadata={
                    "node_name": node_name,
                    "provider": settings.provider,
                    "model": settings.model_name,
                    "llm_runtime": "agent",
                },
            )

            llm = build_langchain_chat_model(settings, enable_native_json_mode=False)
            runtime_agent = create_agent(
                model=llm,
                tools=[],
                system_prompt=system_prompt,
                # response_format=ToolStrategy(pydantic_cls),
                debug=os.getenv("AI_AGENT_ENVIRONMENT", "LOCAL").upper() != "PRODUCTION",
                middleware=build_agent_middlewares(),
            )

            langfuse_session_id = str(state.get(SESSION_ID_KEY) or run_id or "").strip() or None
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
                    llm_runtime="agent",
                ),
            }
            callbacks = [langfuse_handler] if langfuse_handler is not None else []

            result = runtime_agent.invoke(
                {"messages": build_langchain_messages(input_messages)},
                config={"callbacks": callbacks, "metadata": langfuse_metadata},
            )
            content, structured_response = extract_agent_result_content(result)
            if content is None and structured_response is not None:
                content = structured_response
            if settings.parse_json:
                content = parse_json_content(content)

            agent_span_output = {
                "output_key": settings.output_key,
                "status": "success",
            }
            return {**state, settings.output_key: content}

        except Exception as exc:
            agent_span_output = {
                "output_key": settings.output_key,
                "status": "error",
                "error": str(exc),
            }
            log_llm_generation(
                name=node_name or "llm_agent",
                provider=settings.provider,
                model=settings.azure_deployment if settings.provider in ("azure_openai", "azure", "openai") else settings.model_name,
                input_payload=input_messages,
                error=str(exc),
                metadata={
                    "output_key": settings.output_key,
                    "llm_runtime": "agent",
                    **prompt_metadata,
                },
            )
            return {**state, "_error": str(exc), settings.output_key: None}
        finally:
            end_current_runtime_span(
                agent_span,
                agent_scope,
                output_payload=agent_span_output,
            )

    return agent_llm_node
