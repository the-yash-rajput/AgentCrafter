from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from db.session import get_db
from models import Node, Agent
from schemas.schemas import NodeCreate, NodeUpdate, NodeResponse

router = APIRouter(tags=["nodes"])


@router.post("/agents/{agent_id}/nodes", response_model=NodeResponse)
def add_node(agent_id: int, payload: NodeCreate, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    node = Node(
        agent_id=agent_id,
        name=payload.name,
        type=payload.type,
        config=payload.config or {},
        position_x=payload.position_x or 0.0,
        position_y=payload.position_y or 0.0,
    )
    db.add(node)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid node payload: {exc.orig}") from exc
    db.refresh(node)
    return node


@router.put("/nodes/{node_id}", response_model=NodeResponse)
def update_node(node_id: int, payload: NodeUpdate, db: Session = Depends(get_db)):
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(node, key, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid node update: {exc.orig}") from exc
    db.refresh(node)
    return node


@router.delete("/nodes/{node_id}")
def delete_node(node_id: int, db: Session = Depends(get_db)):
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    db.delete(node)
    db.commit()
    return {"message": "Node deleted"}
