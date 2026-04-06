from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.services.agent_exit_nodes import get_agent_exit_nodes
from db.session import get_db
from models import Node, Agent
from backend.services.node_definition import get_node_definitions, resolve_node_definition
from schemas.schemas import NodeCreate, NodeDefinitionResponse, NodeUpdate, NodeResponse

router = APIRouter(tags=["nodes"])


@router.get("/node-definitions", response_model=list[NodeDefinitionResponse])
def list_node_definitions() -> list[NodeDefinitionResponse]:
    return [
        NodeDefinitionResponse(
            type=definition.type,
            subtype=definition.subtype,
            category=definition.category,
            label=definition.label,
            description=definition.description,
            show_in_frontend=definition.show_in_frontend,
            default_config=definition.default_config,
        )
        for definition in get_node_definitions()
    ]


@router.post("/agents/{agent_id}/nodes", response_model=NodeResponse)
def add_node(agent_id: int, payload: NodeCreate, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    node = Node(
        agent_id=agent_id,
        name=payload.name,
        type=payload.type,
        subtype=payload.subtype,
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
    if any(key in update_data for key in ("type", "subtype", "config")):
        incoming_subtype = update_data["subtype"] if "subtype" in update_data else None
        try:
            resolved_type, resolved_subtype, resolved_config = resolve_node_definition(
                update_data.get("type", node.type),
                incoming_subtype,
                update_data.get("config", node.config),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        update_data["type"] = resolved_type
        update_data["subtype"] = resolved_subtype
        update_data["config"] = resolved_config

    previous_name = node.name
    for key, value in update_data.items():
        setattr(node, key, value)

    renamed = "name" in update_data and update_data["name"] != previous_name
    if renamed:
        agent = db.query(Agent).filter(Agent.id == node.agent_id).first()
        if agent:
            if agent.entry_node == previous_name:
                agent.entry_node = node.name
            exit_nodes = [
                node.name if exit_name == previous_name else exit_name
                for exit_name in get_agent_exit_nodes(agent)
            ]
            agent.exit_nodes = exit_nodes
            agent.exit_node = exit_nodes[0] if exit_nodes else None

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

    agent = db.query(Agent).filter(Agent.id == node.agent_id).first()
    if agent:
        if agent.entry_node == node.name:
            agent.entry_node = None
        exit_nodes = [exit_name for exit_name in get_agent_exit_nodes(agent) if exit_name != node.name]
        agent.exit_nodes = exit_nodes
        agent.exit_node = exit_nodes[0] if exit_nodes else None

    db.delete(node)
    db.commit()
    return {"message": "Node deleted"}
