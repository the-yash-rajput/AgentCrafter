from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.error_handling import translate_service_errors
from db.session import get_db
from services.node_service import NodeService
from schemas.schemas import NodeCreate, NodeDefinitionResponse, NodeUpdate, NodeResponse

router = APIRouter(tags=["nodes"])


@router.get("/node-definitions", response_model=list[NodeDefinitionResponse])
@translate_service_errors
def list_node_definitions() -> list[NodeDefinitionResponse]:
    return NodeService.list_node_definitions()


@router.post("/agents/{agent_id}/nodes", response_model=NodeResponse)
@translate_service_errors
def add_node(agent_id: int, payload: NodeCreate, version_id: int | None = None, db: Session = Depends(get_db)):
    return NodeService(db).create_node(agent_id, payload, version_id=version_id)


@router.post("/agents/{agent_id}/versions/{version_id}/nodes", response_model=NodeResponse)
@translate_service_errors
def add_version_node(agent_id: int, version_id: int, payload: NodeCreate, db: Session = Depends(get_db)):
    return NodeService(db).create_node(agent_id, payload, version_id=version_id)


@router.put("/nodes/{node_id}", response_model=NodeResponse)
@translate_service_errors
def update_node(node_id: int, payload: NodeUpdate, db: Session = Depends(get_db)):
    return NodeService(db).update_node(node_id, payload)


@router.delete("/nodes/{node_id}")
@translate_service_errors
def delete_node(node_id: int, db: Session = Depends(get_db)):
    return NodeService(db).delete_node(node_id)
