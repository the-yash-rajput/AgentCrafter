from sqlalchemy.orm import Session
from models.agent_audit import AgentAudit
from agent_exit_nodes import get_agent_exit_nodes
from models import Agent

def record_agent_audit(db: Session, agent_id: int, action: str):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        return
    
    exit_nodes = get_agent_exit_nodes(agent)
    snapshot = {
        "agent": {
            "name": agent.name,
            "description": agent.description,
            "input_schema": agent.input_schema,
            "output_schema": agent.output_schema,
            "state_schema": agent.state_schema,
            "entry_node": agent.entry_node,
            "exit_node": exit_nodes[0] if exit_nodes else None,
            "exit_nodes": exit_nodes,
            "metadata": agent.metadata_
        },
        "nodes": [
            {
                "id": n.id, "name": n.name, "type": n.type.value, "config": n.config,
                "position_x": n.position_x, "position_y": n.position_y
            }
            for n in agent.nodes
        ],
        "edges": [
            {
                "source_node_id": e.source_node_id, "target_node_id": e.target_node_id,
                "edge_type": e.edge_type.value, "condition_config": e.condition_config, "label": e.label
            }
            for e in agent.edges
        ],
    }
    audit = AgentAudit(agent_id=agent_id, action=action, snapshot=snapshot)
    db.add(audit)
