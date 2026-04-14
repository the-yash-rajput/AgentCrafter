from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.error_handling import translate_service_errors
from db.session import get_db
from schemas.schemas import AgentVersionResponse, AgentVersionWithGraph, AgentExportPayload, NodeCreate, NodeResponse, EdgeCreate, EdgeResponse
from services.agent_service import AgentService
from services.agent_version_service import AgentVersionService
from services.agent_io import AgentConfigSerializer
from services.node_service import NodeService
from services.edge_service import EdgeService

router = APIRouter(tags=["versions"])


@router.get("/agents/{agent_id}/versions", response_model=List[AgentVersionResponse])
@translate_service_errors
def list_versions(agent_id: int, db: Session = Depends(get_db)):
    return AgentVersionService(db).list_versions(agent_id)


@router.get("/agents/{agent_id}/versions/{version_id}", response_model=AgentVersionWithGraph)
@translate_service_errors
def get_version(agent_id: int, version_id: int, db: Session = Depends(get_db)):
    return AgentVersionService(db).get_version(version_id, include_graph=True)


@router.post("/agents/{agent_id}/versions/{version_id}/fork", response_model=AgentVersionResponse)
@translate_service_errors
def fork_version(agent_id: int, version_id: int, db: Session = Depends(get_db)):
    return AgentVersionService(db).fork_version(version_id)


@router.get("/agents/{agent_id}/versions/{version_id}/export", response_model=AgentExportPayload)
@translate_service_errors
def export_version(agent_id: int, version_id: int, db: Session = Depends(get_db)):
    agent = AgentService(db).get_agent(agent_id)
    version = AgentVersionService(db).get_version(version_id, include_graph=True)
    return AgentConfigSerializer.serialize(agent, version)


@router.post("/agents/{agent_id}/versions/{version_id}/nodes", response_model=NodeResponse)
@translate_service_errors
def create_node(agent_id: int, version_id: int, payload: NodeCreate, db: Session = Depends(get_db)):
    return NodeService(db).create_node(agent_id, payload, version_id=version_id)


@router.post("/agents/{agent_id}/versions/{version_id}/edges", response_model=EdgeResponse)
@translate_service_errors
def create_edge(agent_id: int, version_id: int, payload: EdgeCreate, db: Session = Depends(get_db)):
    return EdgeService(db).create_edge(agent_id, payload, version_id=version_id)
