from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Edge, Node
from models.agent_version import AgentVersion
from schemas.schemas import EdgeCreate, EdgeUpdate
from services.agent_exit_nodes import get_agent_exit_nodes
from services.exceptions import NotFoundError, ValidationError


class EdgeService:
    def __init__(self, db: Session):
        self.db = db

    def create_edge(self, agent_id: int, payload: EdgeCreate, version_id: int | None = None) -> Edge:
        if version_id is None:
            from services.agent_version_service import AgentVersionService
            version_id = AgentVersionService(self.db).get_or_create_latest(agent_id).id

        version = self.db.query(AgentVersion).filter(AgentVersion.id == version_id).first()
        if not version:
            raise NotFoundError("Version not found")

        source_node = self._get_version_node(version_id, payload.source_node_id)
        target_node = self._get_version_node(version_id, payload.target_node_id)
        if not source_node or not target_node:
            raise ValidationError(
                "source_node_id and target_node_id must reference existing node IDs in this version"
            )
        if source_node.name in get_agent_exit_nodes(version):
            raise ValidationError(f"Cannot add outgoing edges from exit node '{source_node.name}'")

        edge = Edge(
            agent_id=agent_id,
            version_id=version_id,
            source_node_id=payload.source_node_id,
            target_node_id=payload.target_node_id,
            edge_type=payload.edge_type,
            condition_config=payload.condition_config or {},
            label=payload.label,
        )
        self.db.add(edge)
        self._commit_or_raise("Invalid edge payload")
        self.db.refresh(edge)
        return edge

    def update_edge(self, edge_id: int, payload: EdgeUpdate) -> Edge:
        edge = self._get_edge_or_404(edge_id)
        update_data = payload.model_dump(exclude_unset=True)
        version = self.db.query(AgentVersion).filter(AgentVersion.id == edge.version_id).first()

        if "source_node_id" in update_data:
            source = self._get_version_node(edge.version_id, update_data["source_node_id"])
            if not source:
                raise ValidationError("Invalid source_node_id for this version")
            if version and source.name in get_agent_exit_nodes(version):
                raise ValidationError(f"Cannot add outgoing edges from exit node '{source.name}'")

        if "target_node_id" in update_data:
            target = self._get_version_node(edge.version_id, update_data["target_node_id"])
            if not target:
                raise ValidationError("Invalid target_node_id for this version")

        for key, value in update_data.items():
            setattr(edge, key, value)

        self._commit_or_raise("Invalid edge update")
        self.db.refresh(edge)
        return edge

    def delete_edge(self, edge_id: int) -> dict[str, str]:
        edge = self._get_edge_or_404(edge_id)
        self.db.delete(edge)
        self.db.commit()
        return {"message": "Edge deleted"}

    def _get_edge_or_404(self, edge_id: int) -> Edge:
        edge = self.db.query(Edge).filter(Edge.id == edge_id).first()
        if not edge:
            raise NotFoundError("Edge not found")
        return edge

    def _get_version_node(self, version_id: int, node_id: int) -> Node | None:
        return self.db.query(Node).filter(Node.version_id == version_id, Node.id == node_id).first()

    def _commit_or_raise(self, prefix: str) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValidationError(f"{prefix}: {exc.orig}") from exc
