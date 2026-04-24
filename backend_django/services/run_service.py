from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from models import Agent, Run
from models.agent_session import AgentSession
from models.enums import RunStatus
from schemas.schemas import SessionRunCreate
from services.session_history import (
    CONVERSATION_HISTORY_KEY,
    normalize_conversation_history,
)
from services.state_schema import apply_state_schema_defaults
from services.exceptions import NotFoundError, ServiceError, ValidationError
from services.runtime.graph_runner import GraphRunner
from services.runtime.graph_runtime.fetcher import GraphRuntimeRepository
from services.session_service import SessionService


class RunService:
    def __init__(self, db: Session):
        self.db = db

    def start_run(
        self,
        agent_id: int,
        version_id: int,
        session_id: int,
        payload: SessionRunCreate,
    ) -> Run:
        """Validate + create a Run record and return it immediately.

        The caller is responsible for spawning a background thread that calls
        execute_run_background() with the returned run's ID.
        """
        session = self.db.query(AgentSession).filter(AgentSession.id == session_id).first()
        if not session:
            raise NotFoundError("Session not found")

        agent = self._get_agent_or_404(agent_id)
        runner = GraphRunner(self.db)
        validation = runner.validate_graph(agent_id)
        if not validation["valid"]:
            raise ValidationError({"errors": validation["errors"]})

        conversation_history = normalize_conversation_history(session.conversation_history)
        effective_input = apply_state_schema_defaults(payload.metadata, agent.state_schema)

        checkpoint_thread_id = uuid.uuid4()
        repo = GraphRuntimeRepository(self.db)
        run = repo.create_run(
            agent_id,
            {},
            message=payload.message,
            version_id=version_id,
            session_id=session_id,
            checkpoint_thread_id=checkpoint_thread_id,
        )
        # Attach runtime metadata so the background thread can reconstruct the call
        run._runtime_effective_input = dict(effective_input)
        run._runtime_conversation_history = list(conversation_history)
        return run

    def execute_run_background(
        self,
        run_id: int,
        agent_id: int,
        version_id: int,
        session_id: int,
        effective_input: dict,
        conversation_history: list,
        checkpoint_thread_id: uuid.UUID,
        resumed_from_run_id: int | None = None,
        resume_command=None,
    ) -> None:
        """Execute a previously created run in the background.

        Called from a daemon thread with its own DB session.  All exceptions are
        caught internally — compile_and_run already marks the run as
        failed/interrupted before re-raising.
        """
        run = self.db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return

        runtime_input = dict(effective_input)
        runtime_input[CONVERSATION_HISTORY_KEY] = list(conversation_history)
        if run.message:
            runtime_input["message"] = run.message

        runner = GraphRunner(self.db)
        try:
            result = runner.compile_and_run(
                agent_id,
                runtime_input,
                persisted_input_data={k: v for k, v in runtime_input.items() if k != CONVERSATION_HISTORY_KEY},
                session_id=session_id,
                version_id=version_id,
                conversation_history=conversation_history,
                checkpoint_thread_id=checkpoint_thread_id,
                resumed_from_run_id=resumed_from_run_id,
                existing_run=run,
                resume_command=resume_command,
            )
        except Exception:
            # compile_and_run already marked run as failed/interrupted
            result = None

        # Reload to get latest status after execution
        self.db.expire(run)
        run = self.db.query(Run).filter(Run.id == run_id).first()
        if run and run.conversation_turn and run.status == RunStatus.success:
            SessionService(self.db).append_conversation_turn(session_id, run.conversation_turn)

    def resume_run(self, run_id: int, human_response=None) -> Run:
        """Resume an interrupted run from its last LangGraph checkpoint.

        Creates a new Run record that shares the same checkpoint_thread_id so
        LangGraph automatically resumes from the last saved checkpoint state.
        Returns the new run immediately; execution happens in a background thread.

        For confidence-check HITL interruptions, human_response is the approved or
        overridden value to pass back to the interrupted node via Command(resume=...).
        """
        repo = GraphRuntimeRepository(self.db)
        interrupted_run = repo.get_run_for_resume(run_id)

        checkpoint_thread_id = interrupted_run.checkpoint_thread_id
        new_run = repo.create_run(
            interrupted_run.agent_id,
            {},
            message=interrupted_run.message,
            version_id=interrupted_run.version_id,
            session_id=interrupted_run.session_id,
            checkpoint_thread_id=checkpoint_thread_id,
            resumed_from_run_id=run_id,
        )
        # Attach runtime metadata for the background thread
        new_run._runtime_effective_input = {}
        new_run._runtime_conversation_history = []
        new_run._runtime_resumed_from_run_id = run_id
        new_run._runtime_interrupted_session_id = interrupted_run.session_id

        # For confidence-check HITL: build a Command(resume=...) so the executor
        # passes it to graph.invoke() instead of the initial state dict.
        interrupt_meta = dict(interrupted_run.interrupt_metadata or {})
        if interrupt_meta.get("interrupt_type") == "confidence_check":
            from langgraph.types import Command
            new_run._runtime_resume_command = Command(resume=human_response)
        else:
            new_run._runtime_resume_command = None

        return new_run

    def pause_run(self, run_id: int) -> Run:
        """Signal a running run to pause between nodes."""
        run = self.db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise NotFoundError("Run not found")
        if run.status != RunStatus.running:
            raise ValidationError(
                f"Run {run_id} is not running (status: {run.status.value})"
            )
        run.pause_requested = True
        self.db.commit()
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
