from __future__ import annotations

from sqlalchemy.orm import Session

from models import Agent, Run
from schemas.schemas import RunCreate
from services.session_history import (
    CONVERSATION_HISTORY_KEY,
    SESSION_ID_KEY,
    flatten_conversation_history,
    normalize_session_id,
)
from services.state_schema import apply_state_schema_defaults, get_state_schema_session_key
from services.exceptions import NotFoundError, ServiceError, ValidationError
from services.runtime.graph_runner import GraphRunner


class RunService:
    session_history_limit = 20

    def __init__(self, db: Session):
        self.db = db

    def run_agent(self, agent_id: int, payload: RunCreate) -> Run:
        agent = self._get_agent_or_404(agent_id)

        runner = GraphRunner(self.db)
        validation = runner.validate_graph(agent_id)
        if not validation["valid"]:
            raise ValidationError({"errors": validation["errors"]})

        effective_input = apply_state_schema_defaults(payload.input_data, agent.state_schema)
        session_field = get_state_schema_session_key(agent.state_schema)
        derived_session_id = effective_input.get(session_field) if session_field else None
        session_id = normalize_session_id(payload.session_id or derived_session_id)
        conversation_history = self._get_session_conversation(session_id)
        runtime_input = dict(payload.input_data or {})
        execution_context = {
            SESSION_ID_KEY: session_id,
            CONVERSATION_HISTORY_KEY: conversation_history,
        }
        if session_id:
            runtime_input[SESSION_ID_KEY] = session_id
            runtime_input[CONVERSATION_HISTORY_KEY] = conversation_history

        try:
            result = runner.compile_and_run(
                agent_id,
                runtime_input,
                execution_context=execution_context,
                persisted_input_data=payload.input_data,
                session_id=session_id,
                conversation_history=conversation_history,
            )
        except ServiceError:
            raise
        except Exception as exc:
            raise ServiceError(str(exc)) from exc

        return self.get_run(result["run_id"])

    def validate_agent(self, agent_id: int) -> dict:
        self._get_agent_or_404(agent_id)
        return GraphRunner(self.db).validate_graph(agent_id)

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

    def _get_agent_or_404(self, agent_id: int) -> Agent:
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise NotFoundError("Agent not found")
        return agent

    def _get_session_conversation(self, session_id: str | None) -> list[dict[str, str]]:
        if not session_id:
            return []

        prior_runs = (
            self.db.query(Run)
            .filter(Run.session_id == session_id, Run.completed_at.isnot(None))
            .order_by(Run.started_at.desc(), Run.id.desc())
            .limit(self.session_history_limit)
            .all()
        )
        prior_runs.reverse()
        return flatten_conversation_history(prior_runs)
