from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from services.edge_service import EdgeService
from schemas.schemas import EdgeCreate, EdgeUpdate, EdgeResponse

router = APIRouter(tags=["edges"])


@router.post("/agents/{agent_id}/edges", response_model=EdgeResponse)
def add_edge(agent_id: int, payload: EdgeCreate, db: Session = Depends(get_db)):
    return EdgeService(db).create_edge(agent_id, payload)


@router.put("/edges/{edge_id}", response_model=EdgeResponse)
def update_edge(edge_id: int, payload: EdgeUpdate, db: Session = Depends(get_db)):
    return EdgeService(db).update_edge(edge_id, payload)


@router.delete("/edges/{edge_id}")
def delete_edge(edge_id: int, db: Session = Depends(get_db)):
    return EdgeService(db).delete_edge(edge_id)
