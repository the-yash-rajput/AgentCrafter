from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload, noload

from models import Agent, AgentStatus, Edge, Node
from models.agent_version import AgentVersion
from schemas.schemas import AgentCreate, AgentUpdate
from services.exceptions import NotFoundError, ValidationError


class AgentService:
    def __init__(self, db: Session):
        self.db = db

    def create_agent(self, payload: AgentCreate) -> Agent:
        data = payload.model_dump()
        agent = Agent(
            name=data["name"],
            description=data.get("description"),
        )
        self.db.add(agent)
        self._commit_or_raise("Invalid agent payload")
        self.db.refresh(agent)

        from services.agent_version_service import AgentVersionService
        AgentVersionService(self.db).create_initial_version(agent)

        return agent

    def list_agents(self, limit: int = 50, offset: int = 0) -> list[Agent]:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        return (
            self.db.query(Agent)
            .options(
                selectinload(Agent.versions).options(
                    noload(AgentVersion.nodes),
                    noload(AgentVersion.edges),
                    noload(AgentVersion.sessions),
                )
            )
            .order_by(Agent.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_agent(self, agent_id: int, *, include_graph: bool = False) -> Agent:
        query = self.db.query(Agent)
        if include_graph:
            query = query.options(selectinload(Agent.nodes), selectinload(Agent.edges))
        agent = query.filter(Agent.id == agent_id).first()
        if not agent:
            raise NotFoundError("Agent not found")
        return agent

    def update_agent(self, agent_id: int, payload: AgentUpdate) -> Agent:
        agent = self.get_agent(agent_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(agent, key, value)
        self._commit_or_raise("Invalid agent update")
        self.db.refresh(agent)
        return agent

    def delete_agent(self, agent_id: int) -> dict[str, str]:
        agent = self.get_agent(agent_id)
        self.db.delete(agent)
        self.db.commit()
        return {"message": "Agent deleted"}

    def duplicate_agent(self, agent_id: int) -> Agent:
        from services.agent_version_service import AgentVersionService

        source_agent = self.get_agent(agent_id)
        version_svc = AgentVersionService(self.db)
        latest = version_svc.get_latest(agent_id)

        new_agent = Agent(
            name=f"{source_agent.name} (copy)",
            description=source_agent.description,
            status=AgentStatus.draft,
        )
        self.db.add(new_agent)
        self.db.flush()

        if latest:
            source_version = version_svc.get_version(latest.id, include_graph=True)
            new_version = AgentVersion(
                agent_id=new_agent.id,
                version_number=1,
                entry_node=source_version.entry_node,
                exit_nodes=list(source_version.exit_nodes or []),
                state_schema=dict(source_version.state_schema or {}),
            )
            self.db.add(new_version)
            self.db.flush()

            old_to_new: dict[int, int] = {}
            for node in source_version.nodes:
                new_node = Node(
                    agent_id=new_agent.id,
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

            for edge in source_version.edges:
                new_src = old_to_new.get(edge.source_node_id)
                new_tgt = old_to_new.get(edge.target_node_id)
                if new_src and new_tgt:
                    self.db.add(Edge(
                        agent_id=new_agent.id,
                        version_id=new_version.id,
                        source_node_id=new_src,
                        target_node_id=new_tgt,
                        edge_type=edge.edge_type,
                        condition_config=dict(edge.condition_config or {}),
                        label=edge.label,
                    ))
        else:
            self.db.add(AgentVersion(
                agent_id=new_agent.id,
                version_number=1,
            ))

        self._commit_or_raise("Failed to duplicate agent")
        self.db.refresh(new_agent)
        return new_agent

    def _commit_or_raise(self, prefix: str) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValidationError(f"{prefix}: {exc.orig}") from exc
