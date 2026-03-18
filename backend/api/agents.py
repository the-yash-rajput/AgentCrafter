from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from db.session import get_db
from models import Agent, Node, Edge, AgentStatus
from schemas.schemas import AgentCreate, AgentUpdate, AgentResponse, AgentWithGraph

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentResponse)
def create_agent(payload: AgentCreate, db: Session = Depends(get_db)):
    agent = Agent(
        name=payload.name,
        description=payload.description,
        input_schema=payload.input_schema or {},
        output_schema=payload.output_schema or {},
        state_schema=payload.state_schema or {},
        entry_node=payload.entry_node,
        exit_node=payload.exit_node,
        metadata_=payload.metadata_ or {},
    )
    db.add(agent)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid agent payload: {exc.orig}") from exc
    db.refresh(agent)
    return agent


@router.get("", response_model=List[AgentResponse])
def list_agents(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    return db.query(Agent).order_by(Agent.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{agent_id}", response_model=AgentWithGraph)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = (
        db.query(Agent)
        .options(selectinload(Agent.nodes), selectinload(Agent.edges))
        .filter(Agent.id == agent_id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(agent_id: int, payload: AgentUpdate, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "metadata_":
            setattr(agent, "metadata_", value)
        else:
            setattr(agent, key, value)
    
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid agent update: {exc.orig}") from exc
    db.refresh(agent)
    return agent


@router.delete("/{agent_id}")
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(agent)
    db.commit()
    return {"message": "Agent deleted"}


@router.post("/{agent_id}/duplicate", response_model=AgentResponse)
def duplicate_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    new_agent = Agent(
        name=f"{agent.name} (copy)",
        description=agent.description,
        status=AgentStatus.draft,
        input_schema=agent.input_schema,
        output_schema=agent.output_schema,
        state_schema=agent.state_schema,
        entry_node=agent.entry_node,
        exit_node=agent.exit_node,
        metadata_=agent.metadata_,
    )
    db.add(new_agent)
    db.flush()
    node_id_pairs: list[tuple[int, Node]] = []

    for node in agent.nodes:
        new_node = Node(
            agent_id=new_agent.id,
            name=node.name,
            type=node.type,
            config=node.config,
            position_x=node.position_x,
            position_y=node.position_y,
        )
        db.add(new_node)
        node_id_pairs.append((node.id, new_node))
    db.flush()
    node_id_map = {old_id: new_node.id for old_id, new_node in node_id_pairs}

    for edge in agent.edges:
        mapped_source = node_id_map.get(edge.source_node_id)
        mapped_target = node_id_map.get(edge.target_node_id)
        if mapped_source is None or mapped_target is None:
            raise HTTPException(status_code=400, detail="Failed to map edge endpoints while duplicating")
        new_edge = Edge(
            agent_id=new_agent.id,
            source_node_id=mapped_source,
            target_node_id=mapped_target,
            edge_type=edge.edge_type,
            condition_config=edge.condition_config,
            label=edge.label,
        )
        db.add(new_edge)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to duplicate agent: {exc.orig}") from exc
    db.refresh(new_agent)
    return new_agent


@router.get("/{agent_id}/export")
def export_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {
        "agent": {
            "name": agent.name,
            "description": agent.description,
            "input_schema": agent.input_schema,
            "output_schema": agent.output_schema,
            "state_schema": agent.state_schema,
            "entry_node": agent.entry_node,
            "exit_node": agent.exit_node,
        },
        "nodes": [
            {"id": n.id, "name": n.name, "type": n.type.value, "config": n.config,
             "position_x": n.position_x, "position_y": n.position_y}
            for n in agent.nodes
        ],
        "edges": [
            {"source_node_id": e.source_node_id, "target_node_id": e.target_node_id,
             "edge_type": e.edge_type.value, "condition_config": e.condition_config, "label": e.label}
            for e in agent.edges
        ],
    }


@router.post("/import", response_model=AgentResponse)
def import_agent(data: dict, db: Session = Depends(get_db)):
    agent_data = data.get("agent", {})
    new_agent = Agent(**agent_data)
    db.add(new_agent)
    db.flush()

    node_id_map: dict[int, int] = {}
    node_name_map: dict[str, int] = {}
    node_pairs_by_old_id: list[tuple[int, Node]] = []
    created_nodes: list[Node] = []
    for n in data.get("nodes", []):
        raw = dict(n)
        import_node_id = raw.pop("id", None)
        node = Node(agent_id=new_agent.id, **raw)
        db.add(node)
        created_nodes.append(node)
        if import_node_id is not None:
            try:
                node_pairs_by_old_id.append((int(import_node_id), node))
            except (TypeError, ValueError):
                pass
    # Ensure node rows exist before edge FK checks.
    db.flush()
    for old_id, node in node_pairs_by_old_id:
        node_id_map[old_id] = node.id
    for node in created_nodes:
        node_name_map[node.name] = node.id

    for e in data.get("edges", []):
        edge_data = dict(e)
        edge_data.pop("id", None)
        source_ref = edge_data.get("source_node_id")
        target_ref = edge_data.get("target_node_id")

        mapped_source = node_id_map.get(source_ref) if isinstance(source_ref, int) else None
        mapped_target = node_id_map.get(target_ref) if isinstance(target_ref, int) else None
        if mapped_source is None and isinstance(source_ref, str):
            mapped_source = node_name_map.get(source_ref)
        if mapped_target is None and isinstance(target_ref, str):
            mapped_target = node_name_map.get(target_ref)

        if mapped_source is None or mapped_target is None:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid import payload: unable to resolve edge endpoints source={source_ref} target={target_ref}",
            )

        edge_data["source_node_id"] = mapped_source
        edge_data["target_node_id"] = mapped_target
        edge = Edge(agent_id=new_agent.id, **edge_data)
        db.add(edge)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid import payload: {exc.orig}") from exc
    db.refresh(new_agent)
    return new_agent
