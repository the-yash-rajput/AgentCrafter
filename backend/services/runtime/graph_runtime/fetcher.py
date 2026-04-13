from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, load_only

from models import Agent, AgentVersion, Edge, Node, Run, RunStatus
from services.exceptions import NotFoundError
from services.runtime.graph_runtime.dtos import GraphFetchResult
from type_defs import StatePayload


class GraphRuntimeRepository:
    def __init__(self, db: Session):
        self.db = db

    def fetch_for_execution(self, agent_id: int, agent_version_id: int | None = None) -> GraphFetchResult:
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise NotFoundError(f"Agent {agent_id} not found")

        version = self._resolve_version(agent_id, agent_version_id)
        nodes = (
            self.db.query(Node)
            .options(load_only(Node.id, Node.name, Node.type, Node.subtype, Node.config))
            .filter(Node.agent_id == agent_id, Node.agent_version_id == version.id)
            .all()
        )
        edges = (
            self.db.query(Edge)
            .options(
                load_only(
                    Edge.source_node_id,
                    Edge.target_node_id,
                    Edge.edge_type,
                    Edge.condition_config,
                    Edge.label,
                )
            )
            .filter(Edge.agent_id == agent_id, Edge.agent_version_id == version.id)
            .all()
        )
        return GraphFetchResult(agent=agent, version=version, nodes=nodes, edges=edges)

    def fetch_for_validation(self, agent_id: int, agent_version_id: int | None = None) -> GraphFetchResult | None:
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            return None

        version = self._resolve_version(agent_id, agent_version_id)
        nodes = (
            self.db.query(Node)
            .options(load_only(Node.id, Node.name, Node.type, Node.subtype, Node.config))
            .filter(Node.agent_id == agent_id, Node.agent_version_id == version.id)
            .all()
        )
        edges = (
            self.db.query(Edge)
            .options(load_only(Edge.source_node_id, Edge.target_node_id))
            .filter(Edge.agent_id == agent_id, Edge.agent_version_id == version.id)
            .all()
        )
        return GraphFetchResult(agent=agent, version=version, nodes=nodes, edges=edges)

    def fetch_agent_name_maps(self) -> tuple[dict[int, str], dict[str, int]]:
        target_agents_by_id = {
            target_id: name
            for target_id, name in self.db.query(Agent.id, Agent.name).all()
        }
        target_agents_by_name = {name: target_id for target_id, name in target_agents_by_id.items()}
        return target_agents_by_id, target_agents_by_name

    def create_run(
        self,
        agent_id: int,
        input_data: StatePayload,
        *,
        agent_version_id: int | None = None,
        session_id: int | None = None,
        parent_run_id: int | None = None,
    ) -> Run:
        run = Run(
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            session_id=session_id,
            parent_run_id=parent_run_id,
            status=RunStatus.running,
            input_data=dict(input_data or {}),
            output_data={},
            state_snapshots=[],
            started_at=datetime.utcnow(),
        )
        self.db.add(run)
        self.db.commit()
        return run

    def mark_run_success(
        self,
        run: Run,
        output_data: StatePayload,
        snapshots: list[dict],
    ) -> None:
        run.status = RunStatus.success
        run.output_data = output_data
        run.state_snapshots = snapshots
        run.completed_at = datetime.utcnow()
        self.db.commit()

    def mark_run_failed(
        self,
        run: Run,
        error: str,
        snapshots: list[dict],
    ) -> None:
        run.status = RunStatus.failed
        run.error = error
        run.state_snapshots = snapshots
        run.completed_at = datetime.utcnow()
        self.db.commit()

    def get_run_or_404(self, run_id: int) -> Run:
        run = self.db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise NotFoundError("Run not found")
        return run

    def _resolve_version(self, agent_id: int, agent_version_id: int | None) -> AgentVersion:
        query = self.db.query(AgentVersion).filter(AgentVersion.agent_id == agent_id)
        if agent_version_id is not None:
            version = query.filter(AgentVersion.id == agent_version_id).first()
        else:
            version = query.order_by(AgentVersion.version_number.desc()).first()
        if not version:
            raise NotFoundError("Agent version not found")
        return version
