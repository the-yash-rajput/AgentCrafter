import contextvars
from typing import Any, Dict, Optional

from base.utilities.langfuse_client_utility import LangfuseClientWrapper

_current_trace: contextvars.ContextVar[Any] = contextvars.ContextVar("langfuse_current_trace", default=None)


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
        return client.trace(
            name="LangGraph",
            input=_to_serializable(input_data),
            metadata={**metadata, "trace_type": "langgraph"},
            session_id=session_id or run_id,
        )
    except TypeError:
        # Older SDK compatibility.
        try:
            return client.trace(name="LangGraph", metadata={**metadata, "trace_type": "langgraph"})
        except Exception:
            return None
    except Exception:
        return None


def update_run_trace(trace: Any, status: str, output_data: Optional[dict] = None, error: Optional[str] = None):
    if trace is None:
        return

    metadata = {"status": status}
    if error:
        metadata["error"] = error

    try:
        if hasattr(trace, "update"):
            kwargs: Dict[str, Any] = {"metadata": metadata}
            if output_data is not None:
                kwargs["output"] = _to_serializable(output_data)
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
    trace = _current_trace.get()
    if trace is None:
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
        if hasattr(trace, "generation"):
            generation = trace.generation(**kwargs)
            if error and hasattr(generation, "end"):
                generation.end(output=_to_serializable({"error": error}))
            return
    except Exception:
        pass

    try:
        if hasattr(trace, "span"):
            span = trace.span(name=name, input=_to_serializable(input_payload), metadata=_to_serializable(base_metadata))
            if hasattr(span, "end"):
                span.end(output=_to_serializable(output_payload if output_payload is not None else {"error": error}))
    except Exception:
        pass


def log_runtime_event(
    name: str,
    input_payload: Any = None,
    output_payload: Any = None,
    metadata: Optional[dict] = None,
):
    """Log a lightweight runtime span event under the current trace."""
    trace = _current_trace.get()
    if trace is None:
        return

    kwargs: Dict[str, Any] = {
        "name": name,
        "metadata": _to_serializable(metadata or {}),
    }
    if input_payload is not None:
        kwargs["input"] = _to_serializable(input_payload)

    try:
        if hasattr(trace, "span"):
            span = trace.span(**kwargs)
            if hasattr(span, "end"):
                span.end(output=_to_serializable(output_payload))
            return
    except Exception:
        pass


def start_runtime_span(
    name: str,
    input_payload: Any = None,
    metadata: Optional[dict] = None,
):
    """Start a runtime span under the current trace and return it."""
    trace = _current_trace.get()
    if trace is None:
        return None

    kwargs: Dict[str, Any] = {
        "name": name,
        "metadata": _to_serializable(metadata or {}),
    }
    if input_payload is not None:
        kwargs["input"] = _to_serializable(input_payload)

    try:
        if hasattr(trace, "span"):
            return trace.span(**kwargs)
    except Exception:
        return None

    return None


def end_runtime_span(span: Any, output_payload: Any = None):
    if span is None:
        return

    try:
        if hasattr(span, "end"):
            span.end(output=_to_serializable(output_payload))
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
    trace = _current_trace.get()
    if trace is None:
        return None, None

    kwargs: Dict[str, Any] = {
        "as_type": "chain",
        "name": name,
        "metadata": _to_serializable(metadata or {}),
    }
    if input_payload is not None:
        kwargs["input"] = _to_serializable(input_payload)

    try:
        if hasattr(trace, "start_as_current_observation"):
            scope = trace.start_as_current_observation(**kwargs)
            return scope.__enter__(), scope
    except Exception:
        return start_runtime_span(name, input_payload=input_payload, metadata=metadata), None

    return start_runtime_span(name, input_payload=input_payload, metadata=metadata), None


def end_current_runtime_span(
    span: Any,
    scope: Any = None,
    output_payload: Any = None,
):
    end_runtime_span(span, output_payload=output_payload)
    if scope is None:
        return

    try:
        scope.__exit__(None, None, None)
    except Exception:
        pass


def flush_langfuse():
    client = _get_langfuse_client()
    if client is None:
        return
    try:
        if hasattr(client, "flush"):
            client.flush()
    except Exception:
        pass
