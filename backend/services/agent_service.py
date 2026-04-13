from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from models import Agent, AgentStatus, AgentVersion, Edge, Node
from schemas.schemas import AgentCreate, AgentUpdate, AgentVersionCreate, AgentVersionUpdate
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

    def create_agent(self, payload: AgentCreate) -> dict:
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
        self.db.flush()

        version = AgentVersion(
            agent_id=agent.id,
            version_number=1,
            state_schema=deepcopy(agent.state_schema or {}),
            entry_node=agent.entry_node,
            exit_nodes=deepcopy(agent.exit_nodes or []),
            metadata_=deepcopy(agent.metadata_ or {}),
        )
        self.db.add(version)
        self._commit_or_raise("Invalid agent payload")
        return self.get_agent(agent.id, version_id=version.id)

    def list_agents(self, limit: int = 50, offset: int = 0) -> list[dict]:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        agents = (
            self.db.query(Agent)
            .options(selectinload(Agent.versions))
            .order_by(Agent.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._agent_response(agent, self._ensure_default_version(agent)) for agent in agents]

    def get_agent(
        self,
        agent_id: int,
        *,
        include_graph: bool = False,
        version_id: int | None = None,
    ) -> dict:
        query = self.db.query(Agent).options(selectinload(Agent.versions))
        agent = query.filter(Agent.id == agent_id).first()
        if not agent:
            raise NotFoundError("Agent not found")

        version = self._resolve_version(agent, version_id)
        if include_graph:
            version = self._load_version_with_graph(agent.id, version.id)
        return self._agent_response(agent, version, include_graph=include_graph)

    def list_versions(self, agent_id: int) -> list[AgentVersion]:
        agent = self._get_agent_or_404(agent_id)
        self._ensure_default_version(agent)
        return (
            self.db.query(AgentVersion)
            .filter(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.version_number.asc())
            .all()
        )

    def get_agent_version(self, agent_id: int, version_id: int, *, include_graph: bool = False) -> dict:
        agent = self._get_agent_or_404(agent_id)
        version = self._get_version_or_404(agent_id, version_id)
        if include_graph:
            version = self._load_version_with_graph(agent_id, version_id)
        return self._agent_response(agent, version, include_graph=include_graph)

    def create_version_from_base(self, agent_id: int, payload: AgentVersionCreate) -> dict:
        agent = self._get_agent_or_404(agent_id)
        base_version = self._resolve_version(agent, payload.base_version_id)
        base_version = self._load_version_with_graph(agent_id, base_version.id)
        next_number = self._next_version_number(agent_id)

        new_version = AgentVersion(
            agent_id=agent.id,
            version_number=next_number,
            base_version_id=base_version.id,
            state_schema=deepcopy(base_version.state_schema or {}),
            entry_node=base_version.entry_node,
            exit_nodes=deepcopy(base_version.exit_nodes or []),
            metadata_=deepcopy(base_version.metadata_ or {}),
        )
        self.db.add(new_version)
        self.db.flush()

        node_id_map: dict[int, int] = {}
        for node in base_version.nodes:
            copied_node = Node(
                agent_id=agent.id,
                agent_version_id=new_version.id,
                name=node.name,
                type=node.type,
                subtype=node.subtype,
                config=deepcopy(node.config or {}),
                position_x=node.position_x,
                position_y=node.position_y,
            )
            self.db.add(copied_node)
            self.db.flush()
            node_id_map[node.id] = copied_node.id

        for edge in base_version.edges:
            mapped_source = node_id_map.get(edge.source_node_id)
            mapped_target = node_id_map.get(edge.target_node_id)
            if mapped_source is None or mapped_target is None:
                raise ValidationError("Failed to map edge endpoints while creating agent version")
            self.db.add(
                Edge(
                    agent_id=agent.id,
                    agent_version_id=new_version.id,
                    source_node_id=mapped_source,
                    target_node_id=mapped_target,
                    edge_type=edge.edge_type,
                    condition_config=deepcopy(edge.condition_config or {}),
                    label=edge.label,
                )
            )

        self._commit_or_raise("Failed to create agent version")
        return self.get_agent_version(agent_id, new_version.id, include_graph=True)

    def update_agent_version(self, agent_id: int, version_id: int, payload: AgentVersionUpdate) -> dict:
        version = self._get_version_or_404(agent_id, version_id)
        update_data = payload.model_dump(exclude_unset=True)

        if "exit_nodes" in update_data:
            sync_exit_fields(update_data)
            self._validate_exit_nodes(version.id, update_data["exit_nodes"])

        for key, value in update_data.items():
            if key == "metadata_":
                version.metadata_ = value
            else:
                setattr(version, key, value)

        self._mirror_latest_version_fields(version)
        self._commit_or_raise("Invalid agent version update")
        return self.get_agent_version(agent_id, version_id, include_graph=True)

    def update_agent(self, agent_id: int, payload: AgentUpdate) -> dict:
        agent = self._get_agent_or_404(agent_id)
        update_data = _sanitize_agent_payload(payload.model_dump(exclude_unset=True))

        version_update: dict[str, Any] = {}
        for key in ("state_schema", "entry_node", "exit_nodes"):
            if key in update_data:
                version_update[key] = update_data.pop(key)

        if version_update:
            version = self._ensure_default_version(agent)
            if "exit_nodes" in version_update:
                sync_exit_fields(version_update)
                self._validate_exit_nodes(version.id, version_update["exit_nodes"])
            for key, value in version_update.items():
                setattr(version, key, value)
            self._copy_version_fields_to_agent(agent, version)

        for key, value in update_data.items():
            if key == "metadata_":
                agent.metadata_ = value
            else:
                setattr(agent, key, value)

        self._commit_or_raise("Invalid agent update")
        return self.get_agent(agent_id)

    def delete_agent(self, agent_id: int) -> dict[str, str]:
        agent = self._get_agent_or_404(agent_id)
        self.db.delete(agent)
        self.db.commit()
        return {"message": "Agent deleted"}

    def duplicate_agent(self, agent_id: int) -> dict:
        source_agent = self._get_agent_or_404(agent_id)
        source_version = self._load_version_with_graph(
            source_agent.id,
            self._resolve_version(source_agent, None).id,
        )
        new_agent = Agent(
            name=f"{source_agent.name} (copy)",
            description=source_agent.description,
            status=AgentStatus.draft,
            state_schema=deepcopy(source_version.state_schema or {}),
            entry_node=source_version.entry_node,
            exit_nodes=deepcopy(get_agent_exit_nodes(source_version)),
            metadata_=deepcopy(source_agent.metadata_ or {}),
        )
        self.db.add(new_agent)
        self.db.flush()

        new_version = AgentVersion(
            agent_id=new_agent.id,
            version_number=1,
            state_schema=deepcopy(source_version.state_schema or {}),
            entry_node=source_version.entry_node,
            exit_nodes=deepcopy(get_agent_exit_nodes(source_version)),
            metadata_=deepcopy(source_version.metadata_ or {}),
        )
        self.db.add(new_version)
        self.db.flush()

        node_id_map: dict[int, int] = {}
        for node in source_version.nodes:
            new_node = Node(
                agent_id=new_agent.id,
                agent_version_id=new_version.id,
                name=node.name,
                type=node.type,
                subtype=node.subtype,
                config=deepcopy(node.config or {}),
                position_x=node.position_x,
                position_y=node.position_y,
            )
            self.db.add(new_node)
            self.db.flush()
            node_id_map[node.id] = new_node.id

        for edge in source_version.edges:
            mapped_source = node_id_map.get(edge.source_node_id)
            mapped_target = node_id_map.get(edge.target_node_id)
            if mapped_source is None or mapped_target is None:
                raise ValidationError("Failed to map edge endpoints while duplicating")
            self.db.add(
                Edge(
                    agent_id=new_agent.id,
                    agent_version_id=new_version.id,
                    source_node_id=mapped_source,
                    target_node_id=mapped_target,
                    edge_type=edge.edge_type,
                    condition_config=deepcopy(edge.condition_config or {}),
                    label=edge.label,
                )
            )

        self._commit_or_raise("Failed to duplicate agent")
        return self.get_agent(new_agent.id)

    def export_agent(self, agent_id: int, version_id: int | None = None) -> dict:
        agent = self._get_agent_or_404(agent_id)
        version = self._load_version_with_graph(agent.id, self._resolve_version(agent, version_id).id)
        exit_nodes = get_agent_exit_nodes(version)
        return {
            "agent": {
                "name": agent.name,
                "description": agent.description,
                "state_schema": version.state_schema,
                "entry_node": version.entry_node,
                "exit_nodes": exit_nodes,
            },
            "version": {
                "version_number": version.version_number,
                "base_version_id": version.base_version_id,
                "metadata": version.metadata_,
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
                for node in version.nodes
            ],
            "edges": [
                {
                    "source_node_id": edge.source_node_id,
                    "target_node_id": edge.target_node_id,
                    "edge_type": edge.edge_type.value,
                    "condition_config": edge.condition_config,
                    "label": edge.label,
                }
                for edge in version.edges
            ],
        }

    def import_agent(self, data: dict) -> dict:
        agent_data = _sanitize_agent_payload(sync_exit_fields(dict(data.get("agent", {}))))
        version_data = dict(data.get("version") or {})
        new_agent = Agent(
            name=agent_data.get("name") or "Imported Agent",
            description=agent_data.get("description"),
            state_schema=agent_data.get("state_schema") or {},
            entry_node=agent_data.get("entry_node"),
            exit_nodes=agent_data.get("exit_nodes") or [],
            metadata_=agent_data.get("metadata_") or agent_data.get("metadata") or {},
        )
        self.db.add(new_agent)
        self.db.flush()

        version = AgentVersion(
            agent_id=new_agent.id,
            version_number=1,
            state_schema=deepcopy(new_agent.state_schema or {}),
            entry_node=new_agent.entry_node,
            exit_nodes=deepcopy(new_agent.exit_nodes or []),
            metadata_=version_data.get("metadata") or {},
        )
        self.db.add(version)
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

            node = Node(agent_id=new_agent.id, agent_version_id=version.id, **node_data)
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
            self.db.add(Edge(agent_id=new_agent.id, agent_version_id=version.id, **edge_data))

        self._commit_or_raise("Invalid import payload")
        return self.get_agent(new_agent.id)

    def _agent_response(self, agent: Agent, version: AgentVersion, *, include_graph: bool = False) -> dict:
        payload = {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "status": agent.status,
            "state_schema": version.state_schema or {},
            "entry_node": version.entry_node,
            "exit_nodes": get_agent_exit_nodes(version),
            "metadata_": agent.metadata_ or {},
            "versions": list(agent.versions or []),
            "agent_version_id": version.id,
            "version_number": version.version_number,
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
        }
        if include_graph:
            payload["nodes"] = list(version.nodes or [])
            payload["edges"] = list(version.edges or [])
        return payload

    def _resolve_version(self, agent: Agent, version_id: int | None) -> AgentVersion:
        if version_id is not None:
            return self._get_version_or_404(agent.id, version_id)

        versions = list(agent.versions or [])
        if not versions:
            return self._ensure_default_version(agent)
        return max(versions, key=lambda version: int(version.version_number or 0))

    def _ensure_default_version(self, agent: Agent) -> AgentVersion:
        versions = list(agent.versions or [])
        if versions:
            return max(versions, key=lambda version: int(version.version_number or 0))

        version = AgentVersion(
            agent_id=agent.id,
            version_number=1,
            state_schema=deepcopy(agent.state_schema or {}),
            entry_node=agent.entry_node,
            exit_nodes=deepcopy(get_agent_exit_nodes(agent)),
            metadata_=deepcopy(agent.metadata_ or {}),
        )
        self.db.add(version)
        self.db.flush()

        legacy_nodes = self.db.query(Node).filter(Node.agent_id == agent.id, Node.agent_version_id.is_(None)).all()
        for node in legacy_nodes:
            node.agent_version_id = version.id
        legacy_edges = self.db.query(Edge).filter(Edge.agent_id == agent.id, Edge.agent_version_id.is_(None)).all()
        for edge in legacy_edges:
            edge.agent_version_id = version.id

        self.db.commit()
        self.db.refresh(agent)
        self.db.refresh(version)
        return version

    def _load_version_with_graph(self, agent_id: int, version_id: int) -> AgentVersion:
        version = (
            self.db.query(AgentVersion)
            .options(selectinload(AgentVersion.nodes), selectinload(AgentVersion.edges))
            .filter(AgentVersion.agent_id == agent_id, AgentVersion.id == version_id)
            .first()
        )
        if not version:
            raise NotFoundError("Agent version not found")
        return version

    def _get_agent_or_404(self, agent_id: int) -> Agent:
        agent = self.db.query(Agent).options(selectinload(Agent.versions)).filter(Agent.id == agent_id).first()
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

    def _next_version_number(self, agent_id: int) -> int:
        max_number = (
            self.db.query(func.max(AgentVersion.version_number))
            .filter(AgentVersion.agent_id == agent_id)
            .scalar()
        )
        return int(max_number or 0) + 1

    def _validate_exit_nodes(self, agent_version_id: int, exit_nodes: list[str]) -> None:
        node_rows = self.db.query(Node.id, Node.name).filter(Node.agent_version_id == agent_version_id).all()
        name_to_id = {name: node_id for node_id, name in node_rows}
        missing_nodes = [name for name in exit_nodes if name not in name_to_id]
        if missing_nodes:
            raise ValidationError(f"Exit nodes do not exist: {', '.join(missing_nodes)}")

        outgoing_node_ids = {
            source_node_id
            for (source_node_id,) in self.db.query(Edge.source_node_id)
            .filter(Edge.agent_version_id == agent_version_id)
            .distinct()
            .all()
        }
        non_leaf_exit_nodes = [name for name in exit_nodes if name_to_id[name] in outgoing_node_ids]
        if non_leaf_exit_nodes:
            raise ValidationError(f"Exit nodes must be leaf nodes: {', '.join(non_leaf_exit_nodes)}")

    def _mirror_latest_version_fields(self, version: AgentVersion) -> None:
        agent = self.db.query(Agent).options(selectinload(Agent.versions)).filter(Agent.id == version.agent_id).first()
        if not agent:
            return
        latest_version = max(list(agent.versions or [version]), key=lambda item: int(item.version_number or 0))
        if latest_version.id == version.id:
            self._copy_version_fields_to_agent(agent, version)

    @staticmethod
    def _copy_version_fields_to_agent(agent: Agent, version: AgentVersion) -> None:
        agent.state_schema = deepcopy(version.state_schema or {})
        agent.entry_node = version.entry_node
        agent.exit_nodes = deepcopy(get_agent_exit_nodes(version))

    def _commit_or_raise(self, prefix: str) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValidationError(f"{prefix}: {exc.orig}") from exc
