from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Node
from models.agent_version import AgentVersion
from schemas.schemas import NodeCreate, NodeDefinitionResponse, NodeUpdate
from services.agent_exit_nodes import get_agent_exit_nodes
from services.exceptions import NotFoundError, ValidationError
from services.node_definition import get_node_definitions, resolve_node_definition


class NodeService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def list_node_definitions() -> list[NodeDefinitionResponse]:
        return [
            NodeDefinitionResponse(
                type=definition.type,
                subtype=definition.subtype,
                category=definition.category,
                label=definition.label,
                description=definition.description,
                show_in_frontend=definition.show_in_frontend,
                default_config=definition.default_config,
            )
            for definition in get_node_definitions()
        ]

    def create_node(self, agent_id: int, payload: NodeCreate, version_id: int | None = None) -> Node:
        if version_id is None:
            from services.agent_version_service import AgentVersionService
            version_id = AgentVersionService(self.db).get_or_create_latest(agent_id).id

        try:
            resolved_type, resolved_subtype, resolved_config = resolve_node_definition(
                payload.type,
                payload.subtype,
                payload.config,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        node = Node(
            agent_id=agent_id,
            version_id=version_id,
            name=payload.name,
            type=resolved_type,
            subtype=resolved_subtype,
            config=resolved_config,
            position_x=payload.position_x or 0.0,
            position_y=payload.position_y or 0.0,
        )
        self.db.add(node)
        self._commit_or_raise("Invalid node payload")
        self.db.refresh(node)
        return node

    def update_node(self, node_id: int, payload: NodeUpdate) -> Node:
        node = self._get_node_or_404(node_id)
        update_data = payload.model_dump(exclude_unset=True)

        if any(key in update_data for key in ("type", "subtype", "config")):
            incoming_subtype = update_data["subtype"] if "subtype" in update_data else None
            try:
                resolved_type, resolved_subtype, resolved_config = resolve_node_definition(
                    update_data.get("type", node.type),
                    incoming_subtype,
                    update_data.get("config", node.config),
                )
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

            update_data["type"] = resolved_type
            update_data["subtype"] = resolved_subtype
            update_data["config"] = resolved_config

        previous_name = node.name
        for key, value in update_data.items():
            setattr(node, key, value)

        renamed = "name" in update_data and update_data["name"] != previous_name
        if renamed:
            version = self.db.query(AgentVersion).filter(AgentVersion.id == node.version_id).first()
            if version:
                if version.entry_node == previous_name:
                    version.entry_node = node.name
                version.exit_nodes = [
                    node.name if exit_name == previous_name else exit_name
                    for exit_name in get_agent_exit_nodes(version)
                ]

        self._commit_or_raise("Invalid node update")
        self.db.refresh(node)
        return node

    def delete_node(self, node_id: int) -> dict[str, str]:
        node = self._get_node_or_404(node_id)
        version = self.db.query(AgentVersion).filter(AgentVersion.id == node.version_id).first()
        if version:
            if version.entry_node == node.name:
                version.entry_node = None
            version.exit_nodes = [
                exit_name for exit_name in get_agent_exit_nodes(version) if exit_name != node.name
            ]

        self.db.delete(node)
        self.db.commit()
        return {"message": "Node deleted"}

    def _get_node_or_404(self, node_id: int) -> Node:
        node = self.db.query(Node).filter(Node.id == node_id).first()
        if not node:
            raise NotFoundError("Node not found")
        return node

    def _commit_or_raise(self, prefix: str) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValidationError(f"{prefix}: {exc.orig}") from exc
