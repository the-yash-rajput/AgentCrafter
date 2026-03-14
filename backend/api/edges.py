from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from db.session import get_db
from models.models import Edge, Agent, Node
from schemas.schemas import EdgeCreate, EdgeUpdate, EdgeResponse

router = APIRouter(tags=["edges"])


@router.post("/agents/{agent_id}/edges", response_model=EdgeResponse)
def add_edge(agent_id: int, payload: EdgeCreate, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    source_node = db.query(Node).filter(Node.agent_id == agent_id, Node.name == payload.source_node_id).first()
    target_node = db.query(Node).filter(Node.agent_id == agent_id, Node.name == payload.target_node_id).first()
    if not source_node or not target_node:
        raise HTTPException(status_code=400, detail="source_node_id and target_node_id must reference existing agent nodes")

    edge = Edge(
        agent_id=agent_id,
        source_node_id=payload.source_node_id,
        target_node_id=payload.target_node_id,
        edge_type=payload.edge_type,
        condition_config=payload.condition_config or {},
        label=payload.label,
    )
    db.add(edge)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid edge payload: {exc.orig}") from exc
    db.refresh(edge)
    return edge


@router.put("/edges/{edge_id}", response_model=EdgeResponse)
def update_edge(edge_id: int, payload: EdgeUpdate, db: Session = Depends(get_db)):
    edge = db.query(Edge).filter(Edge.id == edge_id).first()
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(edge, key, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid edge update: {exc.orig}") from exc
    db.refresh(edge)
    return edge


@router.delete("/edges/{edge_id}")
def delete_edge(edge_id: int, db: Session = Depends(get_db)):
    edge = db.query(Edge).filter(Edge.id == edge_id).first()
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    db.delete(edge)
    db.commit()
    return {"message": "Edge deleted"}
