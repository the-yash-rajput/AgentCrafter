from __future__ import annotations

from services.runtime.graph_runtime.dtos import CompiledGraphArtifact, GraphRunResult
from type_defs import StatePayload


class LangGraphExecutor:

    def execute(
        self,
        compiled_graph: CompiledGraphArtifact,
        *,
        run_id: int,
        input_data: StatePayload,
        snapshots: list[dict],
        thread_id: str | None = None,
        resume_command=None,
        resume: bool = False,
    ) -> GraphRunResult:
        current_state = dict(input_data or {})
        config = {"configurable": {"thread_id": thread_id}} if thread_id else {}

        if resume_command is not None:
            # Confidence-check HITL: pass Command(resume=...) so LangGraph reloads
            # the checkpoint and returns the human value from interrupt().
            invoke_input = resume_command
        elif resume:
            # Manual-pause resume: LangGraph only reloads a checkpoint when input is
            # None or a Command instance — a plain dict triggers a fresh run from the
            # entry node. Pass an empty Command() so the checkpoint is picked up.
            from langgraph.types import Command
            invoke_input = Command()
        else:
            invoke_input = current_state

        result = compiled_graph.graph.invoke(invoke_input, config)
        if isinstance(result, dict):
            current_state = result
        if "_error" in current_state:
            raise RuntimeError(current_state["_error"])

        return GraphRunResult(
            run_id=run_id,
            status="success",
            output=current_state,
            snapshots=snapshots,
        )
