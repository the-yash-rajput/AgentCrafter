from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Agent, Edge, Node
from schemas.schemas import EdgeCreate, EdgeUpdate
from services.agent_exit_nodes import get_agent_exit_nodes


class EdgeService:
    def __init__(self, db: Session):
        self.db = db

    def create_edge(self, agent_id: int, payload: EdgeCreate) -> Edge:
        agent = self._get_agent_or_404(agent_id)
        source_node = self._get_agent_node(agent_id, payload.source_node_id)
        target_node = self._get_agent_node(agent_id, payload.target_node_id)
        if not source_node or not target_node:
            raise HTTPException(
                status_code=400,
                detail="source_node_id and target_node_id must reference existing node IDs in this agent",
            )
        if source_node.name in get_agent_exit_nodes(agent):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot add outgoing edges from exit node '{source_node.name}'",
            )

        edge = Edge(
            agent_id=agent_id,
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
        agent = self.db.query(Agent).filter(Agent.id == edge.agent_id).first()

        if "source_node_id" in update_data:
            source = self._get_agent_node(edge.agent_id, update_data["source_node_id"])
            if not source:
                raise HTTPException(status_code=400, detail="Invalid source_node_id for this agent")
            if agent and source.name in get_agent_exit_nodes(agent):
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot add outgoing edges from exit node '{source.name}'",
                )

        if "target_node_id" in update_data:
            target = self._get_agent_node(edge.agent_id, update_data["target_node_id"])
            if not target:
                raise HTTPException(status_code=400, detail="Invalid target_node_id for this agent")

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

    def _get_agent_or_404(self, agent_id: int) -> Agent:
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent

    def _get_edge_or_404(self, edge_id: int) -> Edge:
        edge = self.db.query(Edge).filter(Edge.id == edge_id).first()
        if not edge:
            raise HTTPException(status_code=404, detail="Edge not found")
        return edge

    def _get_agent_node(self, agent_id: int, node_id: int) -> Node | None:
        return self.db.query(Node).filter(Node.agent_id == agent_id, Node.id == node_id).first()

    def _commit_or_raise(self, prefix: str) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(status_code=400, detail=f"{prefix}: {exc.orig}") from exc
