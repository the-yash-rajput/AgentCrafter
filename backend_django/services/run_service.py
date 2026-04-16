from __future__ import annotations

from sqlalchemy.orm import Session

from models import Agent, Run
from models.agent_session import AgentSession
from schemas.schemas import SessionRunCreate
from services.session_history import (
    CONVERSATION_HISTORY_KEY,
    normalize_conversation_history,
)
from services.state_schema import apply_state_schema_defaults
from services.exceptions import NotFoundError, ServiceError, ValidationError
from services.runtime.graph_runner import GraphRunner
from services.session_service import SessionService


class RunService:
    def __init__(self, db: Session):
        self.db = db

    def run_in_session(
        self,
        agent_id: int,
        version_id: int,
        session_id: int,
        payload: SessionRunCreate,
    ) -> Run:
        session = self.db.query(AgentSession).filter(AgentSession.id == session_id).first()
        if not session:
            raise NotFoundError("Session not found")

        agent = self._get_agent_or_404(agent_id)
        runner = GraphRunner(self.db)
        validation = runner.validate_graph(agent_id)
        if not validation["valid"]:
            raise ValidationError({"errors": validation["errors"]})

        conversation_history = normalize_conversation_history(session.conversation_history)
        effective_input = apply_state_schema_defaults(payload.input_data, agent.state_schema)
        runtime_input = dict(effective_input)
        runtime_input[CONVERSATION_HISTORY_KEY] = list(conversation_history)

        try:
            result = runner.compile_and_run(
                agent_id,
                runtime_input,
                persisted_input_data=payload.input_data,
                session_id=session_id,
                version_id=version_id,
                conversation_history=conversation_history,
            )
        except ServiceError:
            raise
        except Exception as exc:
            raise ServiceError(str(exc)) from exc

        run = self.get_run(result["run_id"])
        if run.conversation_turn:
            SessionService(self.db).append_conversation_turn(session_id, run.conversation_turn)

        return run

    def resume_run(self, run_id: int) -> Run:
        """Resume an interrupted run from its last LangGraph checkpoint.

        Validates the run is in 'interrupted' state, then creates a new Run
        record that shares the same checkpoint_thread_id so LangGraph
        automatically resumes from the last saved checkpoint state.
        """
        from services.runtime.graph_runtime.fetcher import GraphRuntimeRepository

        repo = GraphRuntimeRepository(self.db)
        interrupted_run = repo.get_run_for_resume(run_id)

        runner = GraphRunner(self.db)
        try:
            result = runner.compile_and_run(
                interrupted_run.agent_id,
                dict(interrupted_run.input_data or {}),
                version_id=interrupted_run.version_id,
                session_id=interrupted_run.session_id,
                checkpoint_thread_id=interrupted_run.checkpoint_thread_id,
                resumed_from_run_id=run_id,
            )
        except ServiceError:
            raise
        except Exception as exc:
            raise ServiceError(str(exc)) from exc

        run = self.get_run(result["run_id"])
        if run.conversation_turn and interrupted_run.session_id:
            SessionService(self.db).append_conversation_turn(
                interrupted_run.session_id, run.conversation_turn
            )
        return run

    def get_run(self, run_id: int) -> Run:
        run = self.db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise NotFoundError("Run not found")
        return run

    def list_runs(self, agent_id: int, limit: int = 50, offset: int = 0) -> list[Run]:
        self._get_agent_or_404(agent_id)
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        return (
            self.db.query(Run)
            .filter(Run.agent_id == agent_id)
            .order_by(Run.started_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def validate_agent(self, agent_id: int) -> dict:
        self._get_agent_or_404(agent_id)
        return GraphRunner(self.db).validate_graph(agent_id)

    def _get_agent_or_404(self, agent_id: int) -> Agent:
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise NotFoundError("Agent not found")
        return agent
