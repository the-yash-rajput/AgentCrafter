from collections import defaultdict
from typing import Any, Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session, load_only
from langgraph.graph import StateGraph, END

from backend.services.agent_exit_nodes import get_agent_exit_nodes
from models import Agent, Node, Edge, Run, RunStatus, NodeSubtype, NodeType, EdgeType
from backend.services.node_definition import resolve_node_definition
from backend.services.runtime.edge_router import build_condition_router
from backend.services.runtime.langfuse_tracing import (
    start_run_trace,
    update_run_trace,
    set_current_trace,
    reset_current_trace,
    flush_langfuse,
)
from backend.services.runtime.nodes.factory import NodeRunnerFactory
from type_defs import ExecutionContext, StatePayload


class GraphRunner:
    def __init__(self, db: Session):
        self.db = db
        self.max_agent_call_depth = 8

    def compile_and_run(
        self,
        agent_id: int,
        input_data: StatePayload,
        execution_context: Optional[ExecutionContext] = None,
    ) -> dict:
        """Fetch agent from DB, compile to LangGraph, and run it."""
        execution_context = execution_context or {}
        prior_call_stack = list(execution_context.get("call_stack") or [])
        if agent_id in prior_call_stack:
            cycle = prior_call_stack + [agent_id]
            raise ValueError(f"Recursive agent call detected: {' -> '.join(map(str, cycle))}")
        if len(prior_call_stack) >= self.max_agent_call_depth:
            raise ValueError(f"Nested agent call depth exceeded limit of {self.max_agent_call_depth}")
        execution_context = {
            **execution_context,
            "call_stack": [*prior_call_stack, agent_id],
        }

        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        nodes = (
            self.db.query(Node)
            .options(load_only(Node.id, Node.name, Node.type, Node.subtype, Node.config))
            .filter(Node.agent_id == agent_id)
            .all()
        )
        edges = (
            self.db.query(Edge)
            .options(load_only(Edge.source_node_id, Edge.target_node_id, Edge.edge_type, Edge.condition_config, Edge.label))
            .filter(Edge.agent_id == agent_id)
            .all()
        )

        if not nodes:
            raise ValueError("Agent has no nodes configured")

        # Create run record
        run = Run(
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
            graph = self._build_langgraph(
                agent,
                nodes,
                edges,
                snapshots,
                execution_context=execution_context,
                run_id=str(run.id),
            )
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
                "run_id": run.id,
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

    def _build_langgraph(
        self,
        agent: Agent,
        nodes: List[Node],
        edges: List[Edge],
        snapshots: list,
        execution_context: Optional[dict] = None,
        run_id: Optional[str] = None,
    ):
        """Compile agent config into an executable LangGraph graph."""
        workflow = StateGraph(dict)
        node_factory = NodeRunnerFactory()

        node_map: Dict[str, Node] = {}
        node_id_to_name: Dict[int, str] = {}
        for node in nodes:
            try:
                fn = node_factory.build(
                    node_type=node.type,
                    subtype=node.subtype,
                    config=node.config or {},
                    db=self.db,
                    current_agent_id=agent.id,
                    execution_context=execution_context,
                    agent_name=agent.name,
                    run_id=run_id,
                    node_name=node.name,
                )
            except ValueError:
                continue

            workflow.add_node(node.name, self._wrap_node(node, fn, snapshots))
            node_map[node.name] = node
            node_id_to_name[node.id] = node.name

        if not node_map:
            raise ValueError("Agent has no executable nodes configured")

        entry_node = agent.entry_node if agent.entry_node in node_map else next(iter(node_map))
        workflow.set_entry_point(entry_node)

        edges_by_source: Dict[str, List[tuple[str, Edge]]] = defaultdict(list)
        for edge in edges:
            source_name = node_id_to_name.get(edge.source_node_id)
            target_name = node_id_to_name.get(edge.target_node_id)
            if source_name and target_name:
                edges_by_source[source_name].append((target_name, edge))

        for source, source_edges in edges_by_source.items():
            conditional_edges = [(target, e) for target, e in source_edges if e.edge_type == EdgeType.conditional]
            direct_edges = [(target, e) for target, e in source_edges if e.edge_type == EdgeType.direct]

            if conditional_edges:
                edge_list = [
                    {"target": target_name, "label": e.label or target_name}
                    for target_name, e in conditional_edges
                ]
                router = build_condition_router(conditional_edges[0][1].condition_config or {}, edge_list)

                def route(state: dict, _router=router):
                    next_node = _router(state)
                    return END if next_node == "__end__" else next_node

                workflow.add_conditional_edges(source, route)
                continue

            for target_name, _edge in direct_edges:
                workflow.add_edge(source, target_name)

        configured_exit_nodes = get_agent_exit_nodes(agent)
        invalid_exit_nodes = [node_name for node_name in configured_exit_nodes if node_name not in node_map]
        if invalid_exit_nodes:
            raise ValueError(f"Exit nodes do not exist: {', '.join(invalid_exit_nodes)}")

        valid_exit_nodes = []
        non_leaf_exit_nodes = []
        for node_name in configured_exit_nodes:
            if edges_by_source.get(node_name):
                non_leaf_exit_nodes.append(node_name)
                continue
            valid_exit_nodes.append(node_name)

        if non_leaf_exit_nodes:
            raise ValueError(f"Exit nodes must be leaf nodes: {', '.join(non_leaf_exit_nodes)}")

        for exit_node in valid_exit_nodes:
            workflow.set_finish_point(exit_node)

        for node_name in node_map:
            if edges_by_source.get(node_name):
                continue
            if node_name in valid_exit_nodes:
                continue
            workflow.add_edge(node_name, END)

        return workflow.compile()

    def _wrap_node(self, node: Node, fn, snapshots: list):
        """Wrap node callables to capture snapshots and fail fast on node errors."""
        def wrapped(state: StatePayload) -> StatePayload:
            before = dict(state)
            result = fn(state)

            if not isinstance(result, dict):
                result = {}

            after = {**before, **result}
            snapshots.append({
                "node_id": str(node.id),
                "node_name": node.name,
                "node_type": node.type.value,
                "node_subtype": node.subtype.value,
                "state_before": before,
                "state_after": after,
                "timestamp": datetime.utcnow().isoformat(),
            })

            if "_error" in result and result["_error"]:
                raise RuntimeError(result["_error"])

            return result

        return wrapped

    def validate_graph(self, agent_id: int) -> dict:
        """Validate the graph configuration."""
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            return {"valid": False, "errors": ["Agent not found"]}

        nodes = (
            self.db.query(Node)
            .options(load_only(Node.id, Node.name, Node.type, Node.subtype, Node.config))
            .filter(Node.agent_id == agent_id)
            .all()
        )
        edges = (
            self.db.query(Edge)
            .options(load_only(Edge.source_node_id, Edge.target_node_id))
            .filter(Edge.agent_id == agent_id)
            .all()
        )

        errors = []
        warnings = []
        node_names = {n.name for n in nodes}
        node_ids = {n.id for n in nodes}
        target_agents_by_id = {
            target_id: name
            for target_id, name in self.db.query(Agent.id, Agent.name).all()
        }
        target_agents_by_name = {name: target_id for target_id, name in target_agents_by_id.items()}

        if not nodes:
            errors.append("Agent has no nodes")

        if agent.entry_node and agent.entry_node not in node_names:
            errors.append(f"Entry node '{agent.entry_node}' does not exist")

        exit_nodes = get_agent_exit_nodes(agent)
        invalid_exit_nodes = [node_name for node_name in exit_nodes if node_name not in node_names]
        if invalid_exit_nodes:
            errors.extend([f"Exit node '{node_name}' does not exist" for node_name in invalid_exit_nodes])

        outgoing_node_ids = {
            source_node_id
            for source_node_id, _target_node_id in (
                (edge.source_node_id, edge.target_node_id) for edge in edges
            )
        }
        node_name_to_id = {node.name: node.id for node in nodes}
        non_leaf_exit_nodes = [
            node_name for node_name in exit_nodes
            if node_name in node_name_to_id and node_name_to_id[node_name] in outgoing_node_ids
        ]
        if non_leaf_exit_nodes:
            errors.extend([f"Exit node '{node_name}' must be a leaf node" for node_name in non_leaf_exit_nodes])

        for node in nodes:
            try:
                resolved_type, resolved_subtype, _resolved_config = resolve_node_definition(
                    node.type,
                    node.subtype,
                    node.config or {},
                )
            except ValueError as exc:
                errors.append(f"Node '{node.name}' is invalid: {exc}")
                continue

            if resolved_type != NodeType.functional or resolved_subtype != NodeSubtype.agent_call:
                continue
            config = node.config or {}
            agent_cfg = config.get("agent_call", {})
            target_agent_id = agent_cfg.get("target_agent_id")
            target_agent_name = str(agent_cfg.get("target_agent_name") or "").strip()

            if target_agent_id in (None, "") and not target_agent_name:
                errors.append(f"Agent Call node '{node.name}' is missing a target agent")
                continue

            resolved_target_id = None
            if target_agent_id not in (None, ""):
                try:
                    resolved_target_id = int(target_agent_id)
                except (TypeError, ValueError):
                    errors.append(f"Agent Call node '{node.name}' has invalid target_agent_id '{target_agent_id}'")
                    continue
                if resolved_target_id not in target_agents_by_id:
                    errors.append(f"Agent Call node '{node.name}' references unknown agent ID '{resolved_target_id}'")
                    continue
            elif target_agent_name:
                resolved_target_id = target_agents_by_name.get(target_agent_name)
                if resolved_target_id is None:
                    errors.append(f"Agent Call node '{node.name}' references unknown agent '{target_agent_name}'")
                    continue

            if resolved_target_id == agent_id:
                errors.append(f"Agent Call node '{node.name}' cannot target the same agent")

        for edge in edges:
            if edge.source_node_id not in node_ids:
                errors.append(f"Edge source node ID '{edge.source_node_id}' does not exist")
            if edge.target_node_id not in node_ids:
                errors.append(f"Edge target node ID '{edge.target_node_id}' does not exist")

        if not agent.entry_node:
            warnings.append("No entry node set — will execute nodes in creation order")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }
