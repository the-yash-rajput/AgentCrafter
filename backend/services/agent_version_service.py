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
            entry_node=agent.entry_node,
            exit_nodes=list(agent.exit_nodes or []),
            state_schema=dict(agent.state_schema or {}),
            metadata_=dict(agent.metadata_ or {}),
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

    def update_version(self, version_id: int, data: dict) -> AgentVersion:
        version = self.get_version(version_id)
        for key, value in data.items():
            setattr(version, key, value)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValidationError(f"Invalid version update: {exc.orig}") from exc
        self.db.refresh(version)
        return version

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
            metadata_=dict(source.metadata_ or {}),
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
