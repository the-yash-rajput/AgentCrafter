from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from services.node_service import NodeService
from schemas.schemas import NodeCreate, NodeDefinitionResponse, NodeUpdate, NodeResponse

router = APIRouter(tags=["nodes"])


@router.get("/node-definitions", response_model=list[NodeDefinitionResponse])
def list_node_definitions() -> list[NodeDefinitionResponse]:
    return NodeService.list_node_definitions()


@router.post("/agents/{agent_id}/nodes", response_model=NodeResponse)
def add_node(agent_id: int, payload: NodeCreate, db: Session = Depends(get_db)):
    return NodeService(db).create_node(agent_id, payload)


@router.put("/nodes/{node_id}", response_model=NodeResponse)
def update_node(node_id: int, payload: NodeUpdate, db: Session = Depends(get_db)):
    return NodeService(db).update_node(node_id, payload)


@router.delete("/nodes/{node_id}")
def delete_node(node_id: int, db: Session = Depends(get_db)):
    return NodeService(db).delete_node(node_id)
