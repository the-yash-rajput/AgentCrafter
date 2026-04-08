from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Dict

from langgraph.graph import END, StateGraph

from models import Edge, EdgeType, Node, NodeType
from services.agent_exit_nodes import get_agent_exit_nodes
from services.runtime.edge_router import build_condition_router
from services.runtime.graph_runtime.dtos import CompiledGraphArtifact, LangGraphBuildRequest
from services.runtime.langfuse_tracing import end_runtime_span, start_runtime_span
from services.runtime.nodes.factory import NodeRunnerFactory
from services.runtime.tool_call_limit import consume_tool_call
from type_defs import ExecutionContext, StatePayload


class LangGraphBuilder:
    
    def __init__(self, db, node_factory: NodeRunnerFactory | None = None):
        self.db = db
        self.node_factory = node_factory or NodeRunnerFactory()

    def compile(self, request: LangGraphBuildRequest) -> CompiledGraphArtifact:
        graph_data = request.graph_data
        agent = graph_data.agent
        nodes = graph_data.nodes
        edges = graph_data.edges

        workflow = StateGraph(dict)
        node_map: Dict[str, Node] = {}
        node_id_to_name: Dict[int, str] = {}

        for node in nodes:
            try:
                fn = self.node_factory.build(
                    node_type=node.type,
                    subtype=node.subtype,
                    config=node.config or {},
                    db=self.db,
                    current_agent_id=agent.id,
                    execution_context=request.execution_context,
                    agent_name=agent.name,
                    run_id=request.run_id,
                    node_name=node.name,
                )
            except ValueError:
                continue

            workflow.add_node(
                node.name,
                self._wrap_node(
                    node,
                    fn,
                    request.snapshots,
                    execution_context=request.execution_context,
                ),
            )
            node_map[node.name] = node
            node_id_to_name[node.id] = node.name

        if not node_map:
            raise ValueError("Agent has no executable nodes configured")

        entry_node = agent.entry_node if agent.entry_node in node_map else next(iter(node_map))
        workflow.set_entry_point(entry_node)

        edges_by_source: Dict[str, list[tuple[str, Edge]]] = defaultdict(list)
        for edge in edges:
            source_name = node_id_to_name.get(edge.source_node_id)
            target_name = node_id_to_name.get(edge.target_node_id)
            if source_name and target_name:
                edges_by_source[source_name].append((target_name, edge))

        for source, source_edges in edges_by_source.items():
            conditional_edges = [
                (target_name, edge) for target_name, edge in source_edges if edge.edge_type == EdgeType.conditional
            ]
            direct_edges = [
                (target_name, edge) for target_name, edge in source_edges if edge.edge_type == EdgeType.direct
            ]

            if conditional_edges:
                edge_list = [
                    {"target": target_name, "label": edge.label or target_name}
                    for target_name, edge in conditional_edges
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

        valid_exit_nodes: list[str] = []
        non_leaf_exit_nodes: list[str] = []
        for node_name in configured_exit_nodes:
            if edges_by_source.get(node_name):
                non_leaf_exit_nodes.append(node_name)
                continue
            valid_exit_nodes.append(node_name)

        if non_leaf_exit_nodes:
            raise ValueError(f"Exit nodes must be leaf nodes: {', '.join(non_leaf_exit_nodes)}")

        for finish_node_name in valid_exit_nodes:
            workflow.set_finish_point(finish_node_name)

        for node_name in node_map:
            if edges_by_source.get(node_name):
                continue
            if node_name in valid_exit_nodes:
                continue
            workflow.add_edge(node_name, END)

        return CompiledGraphArtifact(
            graph=workflow.compile(),
            executable_node_names=set(node_map),
        )

    def _wrap_node(
        self,
        node: Node,
        fn,
        snapshots: list[dict],
        *,
        execution_context: ExecutionContext | None = None,
    ):
        def wrapped(state: StatePayload) -> StatePayload:
            before = dict(state)
            tool_span = None
            tool_span_output: dict | None = None
            try:
                if node.type != NodeType.llm_call:
                    consume_tool_call(execution_context)
                    tool_span = start_runtime_span(
                        name="tools",
                        input_payload={"node_name": node.name},
                        metadata={
                            "node_type": node.type.value,
                            "node_subtype": node.subtype.value,
                        },
                    )

                result = fn(state)

                if not isinstance(result, dict):
                    result = {}

                after = {**before, **result}
                snapshots.append(
                    {
                        "node_id": str(node.id),
                        "node_name": node.name,
                        "node_type": node.type.value,
                        "node_subtype": node.subtype.value,
                        # "node_output": result,
                        "state_before": before,
                        "state_after": after,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

                if "_error" in result and result["_error"]:
                    raise RuntimeError(result["_error"])

                tool_span_output = {
                    "node_name": node.name,
                    "status": "success",
                }
                return result
            except Exception as exc:
                tool_span_output = {
                    "node_name": node.name,
                    "status": "error",
                    "error": str(exc),
                }
                raise
            finally:
                end_runtime_span(tool_span, output_payload=tool_span_output)

        return wrapped
