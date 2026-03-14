import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.session import get_db
from models.models import Edge, Agent
from schemas.schemas import EdgeCreate, EdgeUpdate, EdgeResponse

router = APIRouter(tags=["edges"])


@router.post("/agents/{agent_id}/edges", response_model=EdgeResponse)
def add_edge(agent_id: str, payload: EdgeCreate, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    edge = Edge(
        id=uuid.uuid4(),
        agent_id=agent_id,
        source_node_id=payload.source_node_id,
        target_node_id=payload.target_node_id,
        edge_type=payload.edge_type,
        condition_config=payload.condition_config or {},
        label=payload.label,
    )
    db.add(edge)
    db.commit()
    db.refresh(edge)
    return edge


@router.put("/edges/{edge_id}", response_model=EdgeResponse)
def update_edge(edge_id: str, payload: EdgeUpdate, db: Session = Depends(get_db)):
    edge = db.query(Edge).filter(Edge.id == edge_id).first()
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(edge, key, value)

    db.commit()
    db.refresh(edge)
    return edge


@router.delete("/edges/{edge_id}")
def delete_edge(edge_id: str, db: Session = Depends(get_db)):
    edge = db.query(Edge).filter(Edge.id == edge_id).first()
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    db.delete(edge)
    db.commit()
    return {"message": "Edge deleted"}
