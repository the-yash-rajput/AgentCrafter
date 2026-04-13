from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.error_handling import translate_service_errors
from db.session import get_db
from services.agent_service import AgentService
from schemas.schemas import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
    AgentVersionCreate,
    AgentVersionResponse,
    AgentVersionUpdate,
    AgentWithGraph,
)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentResponse)
@translate_service_errors
def create_agent(payload: AgentCreate, db: Session = Depends(get_db)):
    return AgentService(db).create_agent(payload)


@router.get("", response_model=List[AgentResponse])
@translate_service_errors
def list_agents(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    return AgentService(db).list_agents(limit=limit, offset=offset)


@router.get("/{agent_id}", response_model=AgentWithGraph)
@translate_service_errors
def get_agent(agent_id: int, version_id: int | None = None, db: Session = Depends(get_db)):
    return AgentService(db).get_agent(agent_id, include_graph=True, version_id=version_id)


@router.get("/{agent_id}/versions", response_model=List[AgentVersionResponse])
@translate_service_errors
def list_agent_versions(agent_id: int, db: Session = Depends(get_db)):
    return AgentService(db).list_versions(agent_id)


@router.get("/{agent_id}/versions/{version_id}", response_model=AgentWithGraph)
@translate_service_errors
def get_agent_version(agent_id: int, version_id: int, db: Session = Depends(get_db)):
    return AgentService(db).get_agent_version(agent_id, version_id, include_graph=True)


@router.post("/{agent_id}/versions", response_model=AgentWithGraph)
@translate_service_errors
def create_agent_version(agent_id: int, payload: AgentVersionCreate, db: Session = Depends(get_db)):
    return AgentService(db).create_version_from_base(agent_id, payload)


@router.put("/{agent_id}/versions/{version_id}", response_model=AgentWithGraph)
@translate_service_errors
def update_agent_version(
    agent_id: int,
    version_id: int,
    payload: AgentVersionUpdate,
    db: Session = Depends(get_db),
):
    return AgentService(db).update_agent_version(agent_id, version_id, payload)


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


@router.get("/{agent_id}/export")
@translate_service_errors
def export_agent(agent_id: int, db: Session = Depends(get_db)):
    return AgentService(db).export_agent(agent_id)


@router.post("/import", response_model=AgentResponse)
@translate_service_errors
def import_agent(data: dict, db: Session = Depends(get_db)):
    return AgentService(db).import_agent(data)
