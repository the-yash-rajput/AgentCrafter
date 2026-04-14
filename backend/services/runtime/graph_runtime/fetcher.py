from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, load_only

from models import Agent, Edge, Node, Run, RunStatus
from models.agent_version import AgentVersion


class _VersionedAgentProxy:
    """Combines Agent identity (id, name) with AgentVersion graph fields."""
    __slots__ = ("id", "name", "state_schema", "entry_node", "exit_nodes")

    def __init__(self, agent: Agent, version: AgentVersion) -> None:
        self.id = agent.id
        self.name = agent.name
        self.state_schema = version.state_schema
        self.entry_node = version.entry_node
        self.exit_nodes = version.exit_nodes
from services.exceptions import NotFoundError
from services.runtime.graph_runtime.dtos import GraphFetchResult
from type_defs import StatePayload


class GraphRuntimeRepository:
    def __init__(self, db: Session):
        self.db = db

    def fetch_for_execution(self, agent_id: int, version_id: int | None = None) -> GraphFetchResult:
        if version_id is not None:
            return self._fetch_by_version(version_id)

        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise NotFoundError(f"Agent {agent_id} not found")

        # Fall back to latest version
        version = (
            self.db.query(AgentVersion)
            .filter(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.version_number.desc())
            .first()
        )
        if version:
            return self._fetch_by_version(version.id)

        nodes = (
            self.db.query(Node)
            .options(load_only(Node.id, Node.name, Node.type, Node.subtype, Node.config))
            .filter(Node.agent_id == agent_id)
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
            .filter(Edge.agent_id == agent_id)
            .all()
        )
        return GraphFetchResult(agent=agent, nodes=nodes, edges=edges)

    def _fetch_by_version(self, version_id: int) -> GraphFetchResult:
        version = self.db.query(AgentVersion).filter(AgentVersion.id == version_id).first()
        if not version:
            raise NotFoundError(f"Version {version_id} not found")

        agent = self.db.query(Agent).filter(Agent.id == version.agent_id).first()
        if not agent:
            raise NotFoundError(f"Agent {version.agent_id} not found")

        nodes = (
            self.db.query(Node)
            .options(load_only(Node.id, Node.name, Node.type, Node.subtype, Node.config))
            .filter(Node.version_id == version_id)
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
            .filter(Edge.version_id == version_id)
            .all()
        )
        return GraphFetchResult(agent=_VersionedAgentProxy(agent, version), nodes=nodes, edges=edges)

    def fetch_for_validation(self, agent_id: int, version_id: int | None = None) -> GraphFetchResult | None:
        if version_id is not None:
            version = self.db.query(AgentVersion).filter(AgentVersion.id == version_id).first()
            if not version:
                return None
            nodes = (
                self.db.query(Node)
                .options(load_only(Node.id, Node.name, Node.type, Node.subtype, Node.config))
                .filter(Node.version_id == version_id)
                .all()
            )
            edges = (
                self.db.query(Edge)
                .options(load_only(Edge.source_node_id, Edge.target_node_id))
                .filter(Edge.version_id == version_id)
                .all()
            )
            return GraphFetchResult(agent=version, nodes=nodes, edges=edges)

        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            return None

        version = (
            self.db.query(AgentVersion)
            .filter(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.version_number.desc())
            .first()
        )
        if version:
            return self.fetch_for_validation(agent_id, version_id=version.id)

        nodes = (
            self.db.query(Node)
            .options(load_only(Node.id, Node.name, Node.type, Node.subtype, Node.config))
            .filter(Node.agent_id == agent_id)
            .all()
        )
        edges = (
            self.db.query(Edge)
            .options(load_only(Edge.source_node_id, Edge.target_node_id))
            .filter(Edge.agent_id == agent_id)
            .all()
        )
        return GraphFetchResult(agent=agent, nodes=nodes, edges=edges)

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
        version_id: int | None = None,
        session_id: int | None = None,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> Run:
        run = Run(
            agent_id=agent_id,
            version_id=version_id,
            session_id=session_id,
            status=RunStatus.running,
            input_data=dict(input_data or {}),
            output_data={},
            conversation_turn=[],
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
        *,
        conversation_turn: list[dict[str, str]] | None = None,
    ) -> None:
        run.status = RunStatus.success
        run.output_data = output_data
        run.conversation_turn = list(conversation_turn or [])
        run.state_snapshots = snapshots
        run.completed_at = datetime.utcnow()
        self.db.commit()

    def mark_run_failed(
        self,
        run: Run,
        error: str,
        snapshots: list[dict],
        *,
        conversation_turn: list[dict[str, str]] | None = None,
    ) -> None:
        run.status = RunStatus.failed
        run.error = error
        run.conversation_turn = list(conversation_turn or [])
        run.state_snapshots = snapshots
        run.completed_at = datetime.utcnow()
        self.db.commit()

    def get_run_or_404(self, run_id: int) -> Run:
        run = self.db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise NotFoundError("Run not found")
        return run
