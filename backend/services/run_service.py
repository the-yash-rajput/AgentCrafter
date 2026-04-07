from __future__ import annotations

from sqlalchemy.orm import Session

from models import Agent, Run
from schemas.schemas import RunCreate
from services.exceptions import NotFoundError, ServiceError, ValidationError
from services.runtime.graph_runner import GraphRunner


class RunService:
    def __init__(self, db: Session):
        self.db = db

    def run_agent(self, agent_id: int, payload: RunCreate) -> Run:
        self._get_agent_or_404(agent_id)

        runner = GraphRunner(self.db)
        validation = runner.validate_graph(agent_id)
        if not validation["valid"]:
            raise ValidationError({"errors": validation["errors"]})

        try:
            result = runner.compile_and_run(agent_id, payload.input_data)
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
