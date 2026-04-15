from typing import Optional

from sqlalchemy.orm import Session

from services.agent_exit_nodes import get_agent_exit_nodes
from services.session_history import (
    CONVERSATION_HISTORY_KEY,
    build_conversation_turn,
    normalize_conversation_history,
    strip_session_fields,
)
from services.state_schema import apply_state_schema_defaults
from services.runtime.graph_runtime.builder import LangGraphBuilder
from services.runtime.graph_runtime.dtos import GraphExecutionRequest
from services.runtime.graph_runtime.executor import LangGraphExecutor
from services.runtime.graph_runtime.fetcher import GraphRuntimeRepository
from services.runtime.graph_runtime.tracing import LangGraphTraceService
from services.runtime.graph_runtime.validator import GraphValidator
from type_defs import ExecutionContext, StatePayload


class GraphRunner:
    def __init__(self, db: Session):
        self.db = db
        self.max_agent_call_depth = 8
        self.repository = GraphRuntimeRepository(db)
        self.builder = LangGraphBuilder(db)
        self.trace_service = LangGraphTraceService()
        self.executor = LangGraphExecutor()
        self.validator = GraphValidator()

    def compile_and_run(
        self,
        agent_id: int,
        input_data: StatePayload,
        *,
        execution_context: Optional[ExecutionContext] = None,
        persisted_input_data: Optional[StatePayload] = None,
        session_id: Optional[int] = None,
        version_id: Optional[int] = None,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> dict:
        base_execution_context = dict(execution_context or {})
        resolved_conversation_history = normalize_conversation_history(
            conversation_history
            if conversation_history is not None
            else base_execution_context.get(CONVERSATION_HISTORY_KEY)
        )

        runtime_input = strip_session_fields(input_data)
        if session_id is not None:
            runtime_input[CONVERSATION_HISTORY_KEY] = list(resolved_conversation_history)

        request = GraphExecutionRequest(
            agent_id=agent_id,
            input_data=runtime_input,
            persisted_input_data=strip_session_fields(
                persisted_input_data if persisted_input_data is not None else input_data
            ),
            session_id=session_id,
            conversation_history=list(resolved_conversation_history),
            execution_context={
                **base_execution_context,
                CONVERSATION_HISTORY_KEY: list(resolved_conversation_history),
            },
        ).with_agent_call_stack(max_depth=self.max_agent_call_depth)

        graph_data = self.repository.fetch_for_execution(request.agent_id, version_id=version_id)
        if not graph_data.nodes:
            raise ValueError("Agent has no nodes configured")

        initial_state = apply_state_schema_defaults(request.input_data, graph_data.agent.state_schema)
        persisted_initial_state = apply_state_schema_defaults(
            request.persisted_input_data,
            graph_data.agent.state_schema,
        )

        run = self.repository.create_run(
            request.agent_id,
            persisted_initial_state,
            version_id=version_id,
            session_id=request.session_id,
        )
        snapshots: list[dict] = []
        current_state = dict(initial_state or {})
        trace_session = self.trace_service.start(
            graph_data,
            run,
            current_state,
            execution_context=request.execution_context,
        )
        request.execution_context["langfuse_handler"] = trace_session.callback_handler
        request.execution_context["langfuse_metadata"] = dict(trace_session.metadata or {})
        exit_nodes = set(get_agent_exit_nodes(graph_data.agent))

        try:
            compiled_graph = self.builder.compile(
                request=self._build_request(
                    graph_data=graph_data,
                    snapshots=snapshots,
                    execution_context=request.execution_context,
                    run_id=str(run.id),
                )
            )
            result = self.executor.execute(
                compiled_graph,
                run_id=run.id,
                input_data=current_state,
                snapshots=snapshots,
            )
            current_state = result.output
            persisted_output = strip_session_fields(
                self._resolve_final_output(
                    current_state,
                    snapshots=snapshots,
                    exit_nodes=exit_nodes,
                )
            )
            self.repository.mark_run_success(
                run,
                persisted_output,
                snapshots,
                conversation_turn=build_conversation_turn(
                    persisted_initial_state,
                    agent_output=persisted_output,
                ),
            )
            self.trace_service.mark_success(trace_session, current_state)
            return {
                **result.to_dict(),
                "output": persisted_output,
            }

        except Exception as e:
            persisted_output = strip_session_fields(
                self._resolve_final_output(
                    current_state,
                    snapshots=snapshots,
                    exit_nodes=exit_nodes,
                )
            )
            self.repository.mark_run_failed(
                run,
                str(e),
                snapshots,
                conversation_turn=build_conversation_turn(
                    persisted_initial_state,
                    agent_output=persisted_output,
                    error=str(e),
                ),
            )
            self.trace_service.mark_failure(trace_session, current_state, str(e))
            raise
        finally:
            self.trace_service.close(trace_session)

    def validate_graph(self, agent_id: int) -> dict:
        graph_data = self.repository.fetch_for_validation(agent_id)
        if not graph_data:
            return {"valid": False, "errors": ["Agent not found"]}

        target_agents_by_id, target_agents_by_name = self.repository.fetch_agent_name_maps()
        report = self.validator.validate(
            graph_data,
            target_agents_by_id=target_agents_by_id,
            target_agents_by_name=target_agents_by_name,
        )
        return report.to_dict()

    @staticmethod
    def _build_request(*, graph_data, snapshots, execution_context, run_id):
        from services.runtime.graph_runtime.dtos import LangGraphBuildRequest

        return LangGraphBuildRequest(
            graph_data=graph_data,
            snapshots=snapshots,
            execution_context=execution_context,
            run_id=run_id,
        )

    @staticmethod
    def _resolve_final_output(
        current_state: StatePayload,
        *,
        snapshots: list[dict],
        exit_nodes: set[str],
    ) -> StatePayload:
        if exit_nodes:
            for snapshot in reversed(snapshots):
                if snapshot.get("node_name") not in exit_nodes:
                    continue
                node_output = snapshot.get("node_output")
                if isinstance(node_output, dict):
                    return node_output
                break

        return current_state
