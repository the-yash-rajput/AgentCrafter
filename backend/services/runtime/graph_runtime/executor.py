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
    ) -> GraphRunResult:
        current_state = dict(input_data or {})
        result = compiled_graph.graph.invoke(current_state)
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
