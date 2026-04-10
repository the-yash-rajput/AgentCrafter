from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from models import Agent, AgentStatus, Edge, Node
from schemas.schemas import AgentCreate, AgentUpdate
from services.agent_exit_nodes import get_agent_exit_nodes, sync_exit_fields
from services.exceptions import NotFoundError, ValidationError
from services.node_definition import resolve_node_definition


def _sanitize_agent_payload(payload: dict) -> dict:
    sanitized = dict(payload or {})
    sanitized.pop("input_schema", None)
    sanitized.pop("output_schema", None)
    return sanitized


class AgentService:
    def __init__(self, db: Session):
        self.db = db

    def create_agent(self, payload: AgentCreate) -> Agent:
        payload_data = _sanitize_agent_payload(sync_exit_fields(payload.model_dump(by_alias=False)))
        agent = Agent(
            name=payload_data["name"],
            description=payload_data.get("description"),
            state_schema=payload_data.get("state_schema") or {},
            entry_node=payload_data.get("entry_node"),
            exit_nodes=payload_data.get("exit_nodes") or [],
            metadata_=payload_data.get("metadata_") or {},
        )
        self.db.add(agent)
        self._commit_or_raise("Invalid agent payload")
        self.db.refresh(agent)
        return agent

    def list_agents(self, limit: int = 50, offset: int = 0) -> list[Agent]:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        return self.db.query(Agent).order_by(Agent.created_at.desc()).offset(offset).limit(limit).all()

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
        update_data = _sanitize_agent_payload(payload.model_dump(exclude_unset=True))

        if "exit_nodes" in update_data:
            sync_exit_fields(update_data)
            self._validate_exit_nodes(agent_id, update_data["exit_nodes"])

        for key, value in update_data.items():
            if key == "metadata_":
                setattr(agent, "metadata_", value)
            else:
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
        agent = self.get_agent(agent_id)
        exit_nodes = get_agent_exit_nodes(agent)
        new_agent = Agent(
            name=f"{agent.name} (copy)",
            description=agent.description,
            status=AgentStatus.draft,
            state_schema=agent.state_schema,
            entry_node=agent.entry_node,
            exit_nodes=exit_nodes,
            metadata_=agent.metadata_,
        )
        self.db.add(new_agent)
        self.db.flush()

        node_id_pairs: list[tuple[int, Node]] = []
        for node in agent.nodes:
            new_node = Node(
                agent_id=new_agent.id,
                name=node.name,
                type=node.type,
                subtype=node.subtype,
                config=node.config,
                position_x=node.position_x,
                position_y=node.position_y,
            )
            self.db.add(new_node)
            node_id_pairs.append((node.id, new_node))
        self.db.flush()

        node_id_map = {old_id: new_node.id for old_id, new_node in node_id_pairs}
        for edge in agent.edges:
            mapped_source = node_id_map.get(edge.source_node_id)
            mapped_target = node_id_map.get(edge.target_node_id)
            if mapped_source is None or mapped_target is None:
                raise ValidationError("Failed to map edge endpoints while duplicating")
            self.db.add(
                Edge(
                    agent_id=new_agent.id,
                    source_node_id=mapped_source,
                    target_node_id=mapped_target,
                    edge_type=edge.edge_type,
                    condition_config=edge.condition_config,
                    label=edge.label,
                )
            )

        self._commit_or_raise("Failed to duplicate agent")
        self.db.refresh(new_agent)
        return new_agent

    def export_agent(self, agent_id: int) -> dict:
        agent = self.get_agent(agent_id)
        exit_nodes = get_agent_exit_nodes(agent)
        return {
            "agent": {
                "name": agent.name,
                "description": agent.description,
                "state_schema": agent.state_schema,
                "entry_node": agent.entry_node,
                "exit_nodes": exit_nodes,
            },
            "nodes": [
                {
                    "id": node.id,
                    "name": node.name,
                    "type": node.type.value,
                    "subtype": node.subtype.value,
                    "config": node.config,
                    "position_x": node.position_x,
                    "position_y": node.position_y,
                }
                for node in agent.nodes
            ],
            "edges": [
                {
                    "source_node_id": edge.source_node_id,
                    "target_node_id": edge.target_node_id,
                    "edge_type": edge.edge_type.value,
                    "condition_config": edge.condition_config,
                    "label": edge.label,
                }
                for edge in agent.edges
            ],
        }

    def import_agent(self, data: dict) -> Agent:
        agent_data = _sanitize_agent_payload(sync_exit_fields(dict(data.get("agent", {}))))
        new_agent = Agent(**agent_data)
        self.db.add(new_agent)
        self.db.flush()

        node_id_map: dict[int, int] = {}
        node_name_map: dict[str, int] = {}
        node_pairs_by_old_id: list[tuple[int, Node]] = []
        created_nodes: list[Node] = []

        for raw_node in data.get("nodes", []):
            node_data = dict(raw_node)
            import_node_id = node_data.pop("id", None)
            try:
                node_data["type"], node_data["subtype"], node_data["config"] = resolve_node_definition(
                    node_data.get("type"),
                    node_data.get("subtype"),
                    node_data.get("config"),
                )
            except ValueError as exc:
                raise ValidationError(f"Invalid import payload: {exc}") from exc

            node = Node(agent_id=new_agent.id, **node_data)
            self.db.add(node)
            created_nodes.append(node)
            if import_node_id is not None:
                try:
                    node_pairs_by_old_id.append((int(import_node_id), node))
                except (TypeError, ValueError):
                    pass

        self.db.flush()
        for old_id, node in node_pairs_by_old_id:
            node_id_map[old_id] = node.id
        for node in created_nodes:
            node_name_map[node.name] = node.id

        for raw_edge in data.get("edges", []):
            edge_data = dict(raw_edge)
            edge_data.pop("id", None)
            source_ref = edge_data.get("source_node_id")
            target_ref = edge_data.get("target_node_id")

            mapped_source = node_id_map.get(source_ref) if isinstance(source_ref, int) else None
            mapped_target = node_id_map.get(target_ref) if isinstance(target_ref, int) else None
            if mapped_source is None and isinstance(source_ref, str):
                mapped_source = node_name_map.get(source_ref)
            if mapped_target is None and isinstance(target_ref, str):
                mapped_target = node_name_map.get(target_ref)

            if mapped_source is None or mapped_target is None:
                raise ValidationError(
                    "Invalid import payload: unable to resolve edge endpoints "
                    f"source={source_ref} target={target_ref}"
                )

            edge_data["source_node_id"] = mapped_source
            edge_data["target_node_id"] = mapped_target
            self.db.add(Edge(agent_id=new_agent.id, **edge_data))

        self._commit_or_raise("Invalid import payload")
        self.db.refresh(new_agent)
        return new_agent

    def _validate_exit_nodes(self, agent_id: int, exit_nodes: list[str]) -> None:
        node_rows = self.db.query(Node.id, Node.name).filter(Node.agent_id == agent_id).all()
        name_to_id = {name: node_id for node_id, name in node_rows}
        missing_nodes = [name for name in exit_nodes if name not in name_to_id]
        if missing_nodes:
            raise ValidationError(f"Exit nodes do not exist: {', '.join(missing_nodes)}")

        outgoing_node_ids = {
            source_node_id
            for (source_node_id,) in self.db.query(Edge.source_node_id)
            .filter(Edge.agent_id == agent_id)
            .distinct()
            .all()
        }
        non_leaf_exit_nodes = [name for name in exit_nodes if name_to_id[name] in outgoing_node_ids]
        if non_leaf_exit_nodes:
            raise ValidationError(f"Exit nodes must be leaf nodes: {', '.join(non_leaf_exit_nodes)}")

    def _commit_or_raise(self, prefix: str) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValidationError(f"{prefix}: {exc.orig}") from exc
