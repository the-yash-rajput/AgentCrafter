from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.error_handling import translate_service_errors
from db.session import get_db
from services.agent_service import AgentService
from services.agent_io import AgentConfigSerializer
from schemas.schemas import AgentCreate, AgentUpdate, AgentResponse, AgentWithGraph, AgentListResponse

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentResponse)
@translate_service_errors
def create_agent(payload: AgentCreate, db: Session = Depends(get_db)):
    return AgentService(db).create_agent(payload)


@router.get("", response_model=List[AgentListResponse])
@translate_service_errors
def list_agents(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    return AgentService(db).list_agents(limit=limit, offset=offset)


@router.get("/{agent_id}", response_model=AgentWithGraph)
@translate_service_errors
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    return AgentService(db).get_agent(agent_id, include_graph=True)


@router.put("/{agent_id}", response_model=AgentResponse)
@translate_service_errors
def update_agent(agent_id: int, payload: AgentUpdate, db: Session = Depends(get_db)):
    return AgentService(db).update_agent(agent_id, payload)


@router.delete("/{agent_id}")
@translate_service_errors
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    return AgentService(db).delete_agent(agent_id)


@router.post("/{agent_id}/duplicate", response_model=AgentResponse)
@translate_service_errors
def duplicate_agent(agent_id: int, db: Session = Depends(get_db)):
    return AgentService(db).duplicate_agent(agent_id)


@router.post("/import", response_model=AgentResponse)
@translate_service_errors
def import_agent(data: dict, db: Session = Depends(get_db)):
    return AgentConfigSerializer.deserialize(data, db)
