import contextvars
from dataclasses import dataclass
from typing import Any, Dict, Optional

from base.utilities.langfuse_client_utility import LangfuseClientWrapper

_current_trace: contextvars.ContextVar[Any] = contextvars.ContextVar("langfuse_current_trace", default=None)


@dataclass(slots=True)
class _ObservationScope:
    manager: Any = None
    token: Any = None


def _get_langfuse_client():
    return LangfuseClientWrapper.get_langfuse_client()


def _to_serializable(value: Any):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _to_serializable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_serializable(v) for v in value]
    if isinstance(value, tuple):
        return [_to_serializable(v) for v in value]
    return str(value)


def _build_error_details(output_payload: Any = None) -> str | None:
    if isinstance(output_payload, dict):
        if output_payload.get("status") == "error" and output_payload.get("error") is not None:
            return str(output_payload["error"])
        if output_payload.get("_error") is not None:
            return str(output_payload["_error"])
    return None


def _update_observation(
    observation: Any,
    *,
    output_payload: Any = None,
    error: str | None = None,
    metadata: Optional[dict] = None,
):
    if observation is None or not hasattr(observation, "update"):
        return

    resolved_error = error or _build_error_details(output_payload)
    kwargs: Dict[str, Any] = {}
    if output_payload is not None:
        kwargs["output"] = _to_serializable(output_payload)
    if metadata:
        kwargs["metadata"] = _to_serializable(metadata)
    if resolved_error:
        kwargs["level"] = "ERROR"
        kwargs["status_message"] = resolved_error
    if not kwargs:
        return

    try:
        observation.update(**kwargs)
    except Exception:
        return


def get_current_trace_context() -> dict[str, str] | None:
    observation = _current_trace.get()
    if observation is None:
        return None

    trace_id = getattr(observation, "trace_id", None)
    observation_id = getattr(observation, "id", None)
    if trace_id is None:
        return None

    trace_context = {"trace_id": str(trace_id)}
    if observation_id is not None:
        trace_context["parent_span_id"] = str(observation_id)
    return trace_context


def start_run_trace(
    agent_id: str,
    agent_name: str,
    run_id: str,
    input_data: dict,
    *,
    session_id: str | None = None,
):
    """Create a Langfuse trace for a graph run. Returns trace object or None."""
    client = _get_langfuse_client()
    if client is None:
        return None

    metadata = {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "run_id": run_id,
    }

    try:
        if hasattr(client, "start_observation"):
            trace_kwargs: Dict[str, Any] = {
                "name": "LangGraph",
                "as_type": "chain",
                "input": _to_serializable(input_data),
                "metadata": {**metadata, "trace_type": "langgraph"},
            }
            if session_id:
                trace_kwargs["metadata"]["session_id"] = session_id
            return client.start_observation(**trace_kwargs)
        if hasattr(client, "trace"):
            trace_kwargs = {
                "id": run_id,
                "name": "LangGraph",
                "input": _to_serializable(input_data),
                "metadata": {**metadata, "trace_type": "langgraph"},
            }
            if session_id:
                trace_kwargs["session_id"] = session_id
            return client.trace(**trace_kwargs)
    except Exception:
        return None

    return None


def update_run_trace(
    trace: Any,
    status: str,
    output_data: Optional[dict] = None,
    error: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    if trace is None:
        return

    resolved_metadata = dict(metadata or {})
    resolved_metadata["status"] = status
    if error:
        resolved_metadata["error"] = error

    try:
        if hasattr(trace, "update"):
            kwargs: Dict[str, Any] = {"metadata": _to_serializable(resolved_metadata)}
            if output_data is not None:
                kwargs["output"] = _to_serializable(output_data)
            if error:
                kwargs["level"] = "ERROR"
                kwargs["status_message"] = error
            trace.update(**kwargs)
    except Exception:
        return


def set_current_trace(trace: Any):
    return _current_trace.set(trace)


def reset_current_trace(token):
    try:
        _current_trace.reset(token)
    except Exception:
        pass


def log_llm_generation(
    name: str,
    provider: str,
    model: str,
    input_payload: Any,
    output_payload: Any = None,
    error: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    """Log an LLM generation under the current trace when available."""
    observation = _current_trace.get()
    if observation is None:
        return

    base_metadata = {"provider": provider}
    if metadata:
        base_metadata.update(metadata)
    if error:
        base_metadata["error"] = error

    kwargs: Dict[str, Any] = {
        "name": name,
        "model": model,
        "input": _to_serializable(input_payload),
        "metadata": _to_serializable(base_metadata),
    }
    if output_payload is not None:
        kwargs["output"] = _to_serializable(output_payload)

    try:
        if hasattr(observation, "start_observation"):
            generation = observation.start_observation(as_type="generation", **kwargs)
            _update_observation(
                generation,
                output_payload=output_payload if output_payload is not None else {"error": error} if error else None,
                error=error,
            )
            if hasattr(generation, "end"):
                generation.end()
            return
        if hasattr(observation, "generation"):
            generation = observation.generation(**kwargs)
            _update_observation(
                generation,
                output_payload=output_payload if output_payload is not None else {"error": error} if error else None,
                error=error,
            )
            if hasattr(generation, "end"):
                generation.end()
            return
    except Exception:
        pass

    try:
        if hasattr(observation, "span"):
            span = observation.span(
                name=name,
                input=_to_serializable(input_payload),
                metadata=_to_serializable(base_metadata),
            )
            _update_observation(
                span,
                output_payload=output_payload if output_payload is not None else {"error": error} if error else None,
                error=error,
            )
            if hasattr(span, "end"):
                span.end()
    except Exception:
        pass


def log_runtime_event(
    name: str,
    input_payload: Any = None,
    output_payload: Any = None,
    metadata: Optional[dict] = None,
):
    """Log a lightweight runtime span event under the current trace."""
    observation = _current_trace.get()
    if observation is None:
        return

    kwargs: Dict[str, Any] = {
        "name": name,
        "metadata": _to_serializable(metadata or {}),
    }
    if input_payload is not None:
        kwargs["input"] = _to_serializable(input_payload)

    try:
        if hasattr(observation, "start_observation"):
            span = observation.start_observation(as_type="span", **kwargs)
            _update_observation(span, output_payload=output_payload)
            if hasattr(span, "end"):
                span.end()
            return
        if hasattr(observation, "span"):
            span = observation.span(**kwargs)
            _update_observation(span, output_payload=output_payload)
            if hasattr(span, "end"):
                span.end()
            return
    except Exception:
        pass


def start_runtime_span(
    name: str,
    input_payload: Any = None,
    metadata: Optional[dict] = None,
):
    """Start a runtime span under the current trace and return it."""
    observation = _current_trace.get()
    if observation is None:
        return None

    kwargs: Dict[str, Any] = {
        "name": name,
        "metadata": _to_serializable(metadata or {}),
    }
    if input_payload is not None:
        kwargs["input"] = _to_serializable(input_payload)

    try:
        if hasattr(observation, "start_observation"):
            return observation.start_observation(as_type="span", **kwargs)
        if hasattr(observation, "span"):
            return observation.span(**kwargs)
    except Exception:
        return None

    return None


def end_runtime_span(span: Any, output_payload: Any = None, error: str | None = None):
    if span is None:
        return

    try:
        _update_observation(span, output_payload=output_payload, error=error)
        if hasattr(span, "end"):
            span.end()
    except Exception:
        pass


def start_current_runtime_span(
    name: str,
    input_payload: Any = None,
    metadata: Optional[dict] = None,
):
    """
    Start a child observation as the current Langfuse scope when supported.
    Returns `(observation, scope)` where `scope` is a context manager that must be exited.
    """
    observation = _current_trace.get()
    if observation is None:
        return None, None

    kwargs: Dict[str, Any] = {
        "as_type": "chain",
        "name": name,
        "metadata": _to_serializable(metadata or {}),
    }
    if input_payload is not None:
        kwargs["input"] = _to_serializable(input_payload)

    try:
        if hasattr(observation, "start_as_current_observation"):
            manager = observation.start_as_current_observation(**kwargs)
            child_observation = manager.__enter__()
            return child_observation, _ObservationScope(
                manager=manager,
                token=set_current_trace(child_observation),
            )
    except Exception:
        span = start_runtime_span(name, input_payload=input_payload, metadata=metadata)
        if span is None:
            return None, None
        return span, _ObservationScope(token=set_current_trace(span))

    span = start_runtime_span(name, input_payload=input_payload, metadata=metadata)
    if span is None:
        return None, None
    return span, _ObservationScope(token=set_current_trace(span))


def end_current_runtime_span(
    span: Any,
    scope: Any = None,
    output_payload: Any = None,
):
    wrapped_scope = scope if isinstance(scope, _ObservationScope) else _ObservationScope(manager=scope)
    try:
        if wrapped_scope.manager is not None:
            _update_observation(span, output_payload=output_payload)
            try:
                wrapped_scope.manager.__exit__(None, None, None)
            except Exception:
                pass
        else:
            end_runtime_span(span, output_payload=output_payload)
    finally:
        if wrapped_scope.token is not None:
            reset_current_trace(wrapped_scope.token)


def flush_langfuse():
    client = _get_langfuse_client()
    if client is None:
        return
    try:
        if hasattr(client, "flush"):
            client.flush()
    except Exception:
        pass
