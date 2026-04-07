from __future__ import annotations

from models import Run
from services.runtime.graph_runtime.dtos import GraphFetchResult, TraceSession
from services.runtime.langfuse_tracing import (
    flush_langfuse,
    reset_current_trace,
    set_current_trace,
    start_run_trace,
    update_run_trace,
)
from type_defs import StatePayload


class LangGraphTraceService:
    def start(self, graph_data: GraphFetchResult, run: Run, input_data: StatePayload) -> TraceSession:
        trace = start_run_trace(
            agent_id=str(graph_data.agent.id),
            agent_name=graph_data.agent.name,
            run_id=str(run.id),
            input_data=dict(input_data or {}),
            session_id=run.session_id or str(run.id),
        )
        token = set_current_trace(trace)
        return TraceSession(trace=trace, token=token)

    def mark_success(self, session: TraceSession, output_data: StatePayload) -> None:
        update_run_trace(session.trace, status="success", output_data=output_data)
        flush_langfuse()

    def mark_failure(self, session: TraceSession, output_data: StatePayload, error: str) -> None:
        update_run_trace(session.trace, status="failed", output_data=output_data, error=error)
        flush_langfuse()

    def close(self, session: TraceSession) -> None:
        reset_current_trace(session.token)
