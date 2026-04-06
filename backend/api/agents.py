from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from agent_exit_nodes import get_agent_exit_nodes, sync_exit_fields
from db.session import get_db
from models import Agent, Node, Edge, AgentStatus
from node_definition import resolve_node_definition
from schemas.schemas import AgentCreate, AgentUpdate, AgentResponse, AgentWithGraph

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentResponse)
def create_agent(payload: AgentCreate, db: Session = Depends(get_db)):
    payload_data = sync_exit_fields(payload.model_dump(by_alias=False))
    agent = Agent(
        name=payload_data["name"],
        description=payload_data.get("description"),
        input_schema=payload_data.get("input_schema") or {},
        output_schema=payload_data.get("output_schema") or {},
        state_schema=payload_data.get("state_schema") or {},
        entry_node=payload_data.get("entry_node"),
        exit_node=payload_data.get("exit_node"),
        exit_nodes=payload_data.get("exit_nodes") or [],
        metadata_=payload_data.get("metadata_") or {},
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
    if "exit_node" in update_data or "exit_nodes" in update_data:
        sync_exit_fields(update_data)
        node_rows = (
            db.query(Node.id, Node.name)
            .filter(Node.agent_id == agent_id)
            .all()
        )
        name_to_id = {name: node_id for node_id, name in node_rows}
        missing_nodes = [name for name in update_data["exit_nodes"] if name not in name_to_id]
        if missing_nodes:
            raise HTTPException(
                status_code=400,
                detail=f"Exit nodes do not exist: {', '.join(missing_nodes)}",
            )

        outgoing_node_ids = {
            source_node_id
            for (source_node_id,) in db.query(Edge.source_node_id).filter(Edge.agent_id == agent_id).distinct().all()
        }
        non_leaf_exit_nodes = [
            name for name in update_data["exit_nodes"]
            if name_to_id[name] in outgoing_node_ids
        ]
        if non_leaf_exit_nodes:
            raise HTTPException(
                status_code=400,
                detail=f"Exit nodes must be leaf nodes: {', '.join(non_leaf_exit_nodes)}",
            )

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

    exit_nodes = get_agent_exit_nodes(agent)
    new_agent = Agent(
        name=f"{agent.name} (copy)",
        description=agent.description,
        status=AgentStatus.draft,
        input_schema=agent.input_schema,
        output_schema=agent.output_schema,
        state_schema=agent.state_schema,
        entry_node=agent.entry_node,
        exit_node=(exit_nodes[0] if exit_nodes else None),
        exit_nodes=exit_nodes,
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
            subtype=node.subtype,
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

    exit_nodes = get_agent_exit_nodes(agent)
    return {
        "agent": {
            "name": agent.name,
            "description": agent.description,
            "input_schema": agent.input_schema,
            "output_schema": agent.output_schema,
            "state_schema": agent.state_schema,
            "entry_node": agent.entry_node,
            "exit_node": (exit_nodes[0] if exit_nodes else None),
            "exit_nodes": exit_nodes,
        },
        "nodes": [
            {"id": n.id, "name": n.name, "type": n.type.value, "subtype": n.subtype.value, "config": n.config,
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
    agent_data = sync_exit_fields(dict(data.get("agent", {})))
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
        try:
            raw["type"], raw["subtype"], raw["config"] = resolve_node_definition(
                raw.get("type"),
                raw.get("subtype"),
                raw.get("config"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid import payload: {exc}") from exc
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
