from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from models.agent import Agent
from models.agent_version import AgentVersion
from models.edge import Edge
from models.node import Node
from services.exceptions import NotFoundError, ValidationError


class AgentVersionService:
    def __init__(self, db: Session):
        self.db = db

    def list_versions(self, agent_id: int) -> list[AgentVersion]:
        return (
            self.db.query(AgentVersion)
            .filter(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.version_number.desc())
            .all()
        )

    def get_version(self, version_id: int, *, include_graph: bool = False) -> AgentVersion:
        query = self.db.query(AgentVersion)
        if include_graph:
            query = query.options(selectinload(AgentVersion.nodes), selectinload(AgentVersion.edges))
        version = query.filter(AgentVersion.id == version_id).first()
        if not version:
            raise NotFoundError("Version not found")
        return version

    def get_latest(self, agent_id: int) -> AgentVersion | None:
        return (
            self.db.query(AgentVersion)
            .filter(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.version_number.desc())
            .first()
        )

    def get_or_create_latest(self, agent_id: int) -> AgentVersion:
        latest = self.get_latest(agent_id)
        if latest:
            return latest
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise NotFoundError("Agent not found")
        return self.create_initial_version(agent)

    def create_initial_version(self, agent: Agent) -> AgentVersion:
        version = AgentVersion(
            agent_id=agent.id,
            version_number=1,
        )
        self.db.add(version)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            # Race condition — another request already created version 1
            return self.get_latest(agent.id)
        self.db.refresh(version)
        return version

    def patch_version(self, version_id: int, **fields) -> AgentVersion:
        from sqlalchemy.orm.attributes import flag_modified
        version = self.get_version(version_id, include_graph=True)

        if "state_schema" in fields:
            version.state_schema = fields["state_schema"]
            flag_modified(version, "state_schema")

        if "entry_node" in fields:
            version.entry_node = fields["entry_node"]

        if "exit_nodes" in fields:
            from services.agent_exit_nodes import normalize_exit_nodes
            exit_nodes = normalize_exit_nodes(fields["exit_nodes"])
            self._validate_exit_nodes(version, exit_nodes)
            version.exit_nodes = exit_nodes
            flag_modified(version, "exit_nodes")

        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            raise ValidationError(f"Failed to patch version: {exc}") from exc
        self.db.refresh(version)
        return version

    def _validate_exit_nodes(self, version: AgentVersion, exit_nodes: list[str]) -> None:
        node_names = {n.name for n in version.nodes}
        missing = [name for name in exit_nodes if name not in node_names]
        if missing:
            raise ValidationError(f"Exit nodes do not exist: {', '.join(missing)}")

        outgoing = {e.source_node_id for e in version.edges}
        node_id_by_name = {n.name: n.id for n in version.nodes}
        non_leaf = [name for name in exit_nodes if node_id_by_name.get(name) in outgoing]
        if non_leaf:
            raise ValidationError(f"Exit nodes must be leaf nodes: {', '.join(non_leaf)}")

    def fork_version(self, from_version_id: int) -> AgentVersion:
        source = self.get_version(from_version_id, include_graph=True)
        max_number = (
            self.db.query(func.max(AgentVersion.version_number))
            .filter(AgentVersion.agent_id == source.agent_id)
            .scalar()
        ) or 0

        new_version = AgentVersion(
            agent_id=source.agent_id,
            version_number=max_number + 1,
            entry_node=source.entry_node,
            exit_nodes=list(source.exit_nodes or []),
            state_schema=dict(source.state_schema or {}),
            created_from_version_id=from_version_id,
        )
        self.db.add(new_version)
        self.db.flush()

        old_to_new: dict[int, int] = {}
        for node in source.nodes:
            new_node = Node(
                agent_id=source.agent_id,
                version_id=new_version.id,
                name=node.name,
                type=node.type,
                subtype=node.subtype,
                config=dict(node.config or {}),
                position_x=node.position_x,
                position_y=node.position_y,
            )
            self.db.add(new_node)
            self.db.flush()
            old_to_new[node.id] = new_node.id

        for edge in source.edges:
            new_src = old_to_new.get(edge.source_node_id)
            new_tgt = old_to_new.get(edge.target_node_id)
            if new_src and new_tgt:
                self.db.add(Edge(
                    agent_id=source.agent_id,
                    version_id=new_version.id,
                    source_node_id=new_src,
                    target_node_id=new_tgt,
                    edge_type=edge.edge_type,
                    condition_config=dict(edge.condition_config or {}),
                    label=edge.label,
                ))

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValidationError(f"Failed to fork version: {exc.orig}") from exc

        self.db.refresh(new_version)
        return new_version
