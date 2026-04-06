from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from services.agent_service import AgentService
from schemas.schemas import AgentCreate, AgentUpdate, AgentResponse, AgentWithGraph

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentResponse)
def create_agent(payload: AgentCreate, db: Session = Depends(get_db)):
    return AgentService(db).create_agent(payload)


@router.get("", response_model=List[AgentResponse])
def list_agents(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    return AgentService(db).list_agents(limit=limit, offset=offset)


@router.get("/{agent_id}", response_model=AgentWithGraph)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    return AgentService(db).get_agent(agent_id, include_graph=True)


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(agent_id: int, payload: AgentUpdate, db: Session = Depends(get_db)):
    return AgentService(db).update_agent(agent_id, payload)


@router.delete("/{agent_id}")
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    return AgentService(db).delete_agent(agent_id)


@router.post("/{agent_id}/duplicate", response_model=AgentResponse)
def duplicate_agent(agent_id: int, db: Session = Depends(get_db)):
    return AgentService(db).duplicate_agent(agent_id)


@router.get("/{agent_id}/export")
def export_agent(agent_id: int, db: Session = Depends(get_db)):
    return AgentService(db).export_agent(agent_id)


@router.post("/import", response_model=AgentResponse)
def import_agent(data: dict, db: Session = Depends(get_db)):
    return AgentService(db).import_agent(data)
