import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, END

from models.models import Agent, Node, Edge, Run, RunStatus, NodeType, EdgeType
from runtime.node_builders import build_functional_node, build_llm_node, build_condition_router
from runtime.langfuse_tracing import (
    start_run_trace,
    update_run_trace,
    set_current_trace,
    reset_current_trace,
    flush_langfuse,
)


class GraphRunner:
    def __init__(self, db: Session):
        self.db = db

    def compile_and_run(self, agent_id: str, input_data: dict) -> dict:
        """Fetch agent from DB, compile to LangGraph, and run it."""
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        nodes = self.db.query(Node).filter(Node.agent_id == agent_id).all()
        edges = self.db.query(Edge).filter(Edge.agent_id == agent_id).all()

        if not nodes:
            raise ValueError("Agent has no nodes configured")

        # Create run record
        run = Run(
            id=uuid.uuid4(),
            agent_id=agent_id,
            status=RunStatus.running,
            input_data=input_data,
            output_data={},
            state_snapshots=[],
            started_at=datetime.utcnow(),
        )
        self.db.add(run)
        self.db.commit()

        snapshots = []
        current_state = dict(input_data or {})
        trace = start_run_trace(
            agent_id=str(agent.id),
            agent_name=agent.name,
            run_id=str(run.id),
            input_data=current_state,
        )
        trace_token = set_current_trace(trace)

        try:
            graph = self._build_langgraph(agent, nodes, edges, snapshots)
            result = graph.invoke(current_state)
            if isinstance(result, dict):
                current_state = result
            if "_error" in current_state:
                raise RuntimeError(current_state["_error"])

            # Update run as success
            run.status = RunStatus.success
            run.output_data = current_state
            run.state_snapshots = snapshots
            run.completed_at = datetime.utcnow()
            self.db.commit()
            update_run_trace(trace, status="success", output_data=current_state)
            flush_langfuse()

            return {
                "run_id": str(run.id),
                "status": "success",
                "output": current_state,
                "snapshots": snapshots,
            }

        except Exception as e:
            run.status = RunStatus.failed
            run.error = str(e)
            run.state_snapshots = snapshots
            run.completed_at = datetime.utcnow()
            self.db.commit()
            update_run_trace(trace, status="failed", output_data=current_state, error=str(e))
            flush_langfuse()
            raise
        finally:
            reset_current_trace(trace_token)

    def _build_langgraph(self, agent: Agent, nodes: List[Node], edges: List[Edge], snapshots: list):
        """Compile agent config into an executable LangGraph graph."""
        workflow = StateGraph(dict)

        node_map: Dict[str, Node] = {}
        for node in nodes:
            if node.type == NodeType.functional:
                fn = build_functional_node(node.config or {})
            elif node.type == NodeType.llm_call:
                fn = build_llm_node(node.config or {})
            else:
                continue

            workflow.add_node(node.name, self._wrap_node(node, fn, snapshots))
            node_map[node.name] = node

        if not node_map:
            raise ValueError("Agent has no executable nodes configured")

        entry_node = agent.entry_node if agent.entry_node in node_map else next(iter(node_map))
        workflow.set_entry_point(entry_node)

        edges_by_source: Dict[str, List[Edge]] = defaultdict(list)
        for edge in edges:
            if edge.source_node_id in node_map and edge.target_node_id in node_map:
                edges_by_source[edge.source_node_id].append(edge)

        for source, source_edges in edges_by_source.items():
            conditional_edges = [e for e in source_edges if e.edge_type == EdgeType.conditional]
            direct_edges = [e for e in source_edges if e.edge_type == EdgeType.direct]

            if conditional_edges:
                edge_list = [
                    {"target": e.target_node_id, "label": e.label or e.target_node_id}
                    for e in conditional_edges
                ]
                router = build_condition_router(conditional_edges[0].condition_config or {}, edge_list)

                def route(state: dict, _router=router):
                    next_node = _router(state)
                    return END if next_node == "__end__" else next_node

                workflow.add_conditional_edges(source, route)
                continue

            for edge in direct_edges:
                workflow.add_edge(source, edge.target_node_id)

        valid_exit = agent.exit_node if agent.exit_node in node_map else None
        if valid_exit:
            workflow.set_finish_point(valid_exit)

        for node_name in node_map:
            if edges_by_source.get(node_name):
                continue
            if valid_exit and node_name == valid_exit:
                continue
            workflow.add_edge(node_name, END)

        return workflow.compile()

    def _wrap_node(self, node: Node, fn, snapshots: list):
        """Wrap node callables to capture snapshots and fail fast on node errors."""
        def wrapped(state: dict) -> dict:
            before = dict(state)
            result = fn(state)

            if not isinstance(result, dict):
                result = {}

            after = {**before, **result}
            snapshots.append({
                "node_id": str(node.id),
                "node_name": node.name,
                "node_type": node.type.value,
                "state_before": before,
                "state_after": after,
                "timestamp": datetime.utcnow().isoformat(),
            })

            if "_error" in result and result["_error"]:
                raise RuntimeError(result["_error"])

            return result

        return wrapped

    def validate_graph(self, agent_id: str) -> dict:
        """Validate the graph configuration."""
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            return {"valid": False, "errors": ["Agent not found"]}

        nodes = self.db.query(Node).filter(Node.agent_id == agent_id).all()
        edges = self.db.query(Edge).filter(Edge.agent_id == agent_id).all()

        errors = []
        warnings = []
        node_names = {n.name for n in nodes}

        if not nodes:
            errors.append("Agent has no nodes")

        if agent.entry_node and agent.entry_node not in node_names:
            errors.append(f"Entry node '{agent.entry_node}' does not exist")

        if agent.exit_node and agent.exit_node not in node_names:
            errors.append(f"Exit node '{agent.exit_node}' does not exist")

        for edge in edges:
            if edge.source_node_id not in node_names:
                errors.append(f"Edge source '{edge.source_node_id}' does not exist")
            if edge.target_node_id not in node_names:
                errors.append(f"Edge target '{edge.target_node_id}' does not exist")

        if not agent.entry_node:
            warnings.append("No entry node set — will execute nodes in creation order")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }
