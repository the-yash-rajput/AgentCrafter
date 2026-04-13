from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from models import Agent, AgentSession, AgentVersion, Run
from schemas.schemas import AgentSessionCreate, RunCreate
from services.exceptions import NotFoundError, ServiceError, ValidationError
from services.runtime.graph_runner import GraphRunner
from services.session_history import (
    CONVERSATION_HISTORY_KEY,
    SESSION_ID_KEY,
    normalize_conversation_history,
    normalize_session_id,
)
from services.state_schema import apply_state_schema_defaults


class RunService:
    def __init__(self, db: Session):
        self.db = db

    def create_session(self, agent_id: int, agent_version_id: int, payload: AgentSessionCreate) -> AgentSession:
        self._get_agent_or_404(agent_id)
        version = self._get_version_or_404(agent_id, agent_version_id)
        session = AgentSession(
            agent_id=agent_id,
            agent_version_id=version.id,
            conversation_history=[],
            metadata_=payload.metadata_ or {},
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, agent_id: int, agent_version_id: int, session_id: int) -> AgentSession:
        self._get_agent_or_404(agent_id)
        self._get_version_or_404(agent_id, agent_version_id)
        session = (
            self.db.query(AgentSession)
            .filter(
                AgentSession.id == session_id,
                AgentSession.agent_id == agent_id,
                AgentSession.agent_version_id == agent_version_id,
            )
            .first()
        )
        if not session:
            raise NotFoundError("Agent session not found")
        return session

    def run_agent(self, agent_id: int, payload: RunCreate) -> dict:
        agent = self._get_agent_or_404(agent_id)
        version = self._resolve_latest_version(agent.id)
        session_id = normalize_session_id(payload.session_id)
        if session_id:
            session = self.get_session(agent.id, version.id, session_id)
        else:
            session = self.create_session(agent.id, version.id, AgentSessionCreate())
        return self.run_agent_version(agent.id, version.id, session.id, payload)

    def run_agent_version(
        self,
        agent_id: int,
        agent_version_id: int,
        session_id: int,
        payload: RunCreate,
    ) -> dict:
        agent = self._get_agent_or_404(agent_id)
        version = self._get_version_or_404(agent_id, agent_version_id)
        session = self.get_session(agent.id, version.id, session_id)

        runner = GraphRunner(self.db)
        validation = runner.validate_graph(agent.id, version.id)
        if not validation["valid"]:
            raise ValidationError({"errors": validation["errors"]})

        conversation_history = normalize_conversation_history(session.conversation_history)
        effective_input = apply_state_schema_defaults(payload.input_data, version.state_schema)
        runtime_input = dict(effective_input or {})
        runtime_input[SESSION_ID_KEY] = session.id
        runtime_input[CONVERSATION_HISTORY_KEY] = conversation_history
        execution_context = {
            SESSION_ID_KEY: session.id,
            CONVERSATION_HISTORY_KEY: conversation_history,
        }

        try:
            result = runner.compile_and_run(
                agent.id,
                runtime_input,
                agent_version_id=version.id,
                execution_context=execution_context,
                persisted_input_data=payload.input_data,
                session_id=session.id,
                conversation_history=conversation_history,
            )
        except ServiceError:
            raise
        except Exception as exc:
            raise ServiceError(str(exc)) from exc

        conversation_turn = normalize_conversation_history(result.get("conversation_turn"))
        if conversation_turn:
            session.conversation_history = [*conversation_history, *conversation_turn]
        else:
            session.conversation_history = conversation_history
        session.last_run_at = datetime.utcnow()
        self.db.commit()

        run = self.get_run(result["run_id"])
        return self._run_response(
            run,
            conversation_history=session.conversation_history,
            conversation_turn=conversation_turn,
        )

    def validate_agent(self, agent_id: int, agent_version_id: int | None = None) -> dict:
        self._get_agent_or_404(agent_id)
        if agent_version_id is not None:
            self._get_version_or_404(agent_id, agent_version_id)
        return GraphRunner(self.db).validate_graph(agent_id, agent_version_id)

    def get_run(self, run_id: int) -> Run:
        run = self.db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise NotFoundError("Run not found")
        return run

    def list_runs(
        self,
        agent_id: int,
        *,
        agent_version_id: int | None = None,
        session_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Run]:
        self._get_agent_or_404(agent_id)
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        query = self.db.query(Run).filter(Run.agent_id == agent_id)
        if agent_version_id is not None:
            query = query.filter(Run.agent_version_id == agent_version_id)
        if session_id is not None:
            query = query.filter(Run.session_id == session_id)
        return query.order_by(Run.started_at.desc()).offset(offset).limit(limit).all()

    def _run_response(
        self,
        run: Run,
        *,
        conversation_history: list[dict[str, str]] | None = None,
        conversation_turn: list[dict[str, str]] | None = None,
    ) -> dict:
        return {
            "id": run.id,
            "agent_id": run.agent_id,
            "agent_version_id": run.agent_version_id,
            "session_id": run.session_id,
            "parent_run_id": run.parent_run_id,
            "status": run.status,
            "input_data": run.input_data,
            "output_data": run.output_data,
            "conversation_history": list(conversation_history or []),
            "conversation_turn": list(conversation_turn or []),
            "state_snapshots": run.state_snapshots,
            "error": run.error,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
        }

    def _get_agent_or_404(self, agent_id: int) -> Agent:
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise NotFoundError("Agent not found")
        return agent

    def _get_version_or_404(self, agent_id: int, version_id: int) -> AgentVersion:
        version = (
            self.db.query(AgentVersion)
            .filter(AgentVersion.agent_id == agent_id, AgentVersion.id == version_id)
            .first()
        )
        if not version:
            raise NotFoundError("Agent version not found")
        return version

    def _resolve_latest_version(self, agent_id: int) -> AgentVersion:
        version = (
            self.db.query(AgentVersion)
            .filter(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.version_number.desc())
            .first()
        )
        if not version:
            raise NotFoundError("Agent version not found")
        return version
