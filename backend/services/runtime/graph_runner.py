from typing import Optional

from sqlalchemy.orm import Session

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
        execution_context: Optional[ExecutionContext] = None,
    ) -> dict:
        request = GraphExecutionRequest(
            agent_id=agent_id,
            input_data=dict(input_data or {}),
            execution_context=execution_context or {},
        ).with_agent_call_stack(max_depth=self.max_agent_call_depth)

        graph_data = self.repository.fetch_for_execution(request.agent_id)
        if not graph_data.nodes:
            raise ValueError("Agent has no nodes configured")

        run = self.repository.create_run(request.agent_id, request.input_data)
        snapshots: list[dict] = []
        current_state = dict(request.input_data or {})
        trace_session = self.trace_service.start(graph_data, run, current_state)

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
            self.repository.mark_run_success(run, current_state, snapshots)
            self.trace_service.mark_success(trace_session, current_state)
            return result.to_dict()

        except Exception as e:
            self.repository.mark_run_failed(run, str(e), snapshots)
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
