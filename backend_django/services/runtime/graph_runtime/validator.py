from __future__ import annotations

from models import NodeSubtype, NodeType
from services.agent_exit_nodes import get_agent_exit_nodes
from services.node_definition import resolve_node_definition
from services.runtime.graph_runtime.dtos import GraphFetchResult, GraphValidationReport


class GraphValidator:
    def validate(
        self,
        graph_data: GraphFetchResult,
        *,
        target_agents_by_id: dict[int, str],
        target_agents_by_name: dict[str, int],
    ) -> GraphValidationReport:
        agent = graph_data.agent
        nodes = graph_data.nodes
        edges = graph_data.edges

        errors: list[str] = []
        warnings: list[str] = []
        node_names = {node.name for node in nodes}
        node_ids = {node.id for node in nodes}

        if not nodes:
            errors.append("Agent has no nodes")

        if agent.entry_node and agent.entry_node not in node_names:
            errors.append(f"Entry node '{agent.entry_node}' does not exist")

        exit_nodes = get_agent_exit_nodes(agent)
        invalid_exit_nodes = [node_name for node_name in exit_nodes if node_name not in node_names]
        if invalid_exit_nodes:
            errors.extend([f"Exit node '{node_name}' does not exist" for node_name in invalid_exit_nodes])

        outgoing_node_ids = {edge.source_node_id for edge in edges}
        node_name_to_id = {node.name: node.id for node in nodes}
        non_leaf_exit_nodes = [
            node_name
            for node_name in exit_nodes
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
                    errors.append(
                        f"Agent Call node '{node.name}' has invalid target_agent_id '{target_agent_id}'"
                    )
                    continue
                if resolved_target_id not in target_agents_by_id:
                    errors.append(
                        f"Agent Call node '{node.name}' references unknown agent ID '{resolved_target_id}'"
                    )
                    continue
            elif target_agent_name:
                resolved_target_id = target_agents_by_name.get(target_agent_name)
                if resolved_target_id is None:
                    errors.append(
                        f"Agent Call node '{node.name}' references unknown agent '{target_agent_name}'"
                    )
                    continue

            if resolved_target_id == agent.id:
                errors.append(f"Agent Call node '{node.name}' cannot target the same agent")

        for edge in edges:
            if edge.source_node_id not in node_ids:
                errors.append(f"Edge source node ID '{edge.source_node_id}' does not exist")
            if edge.target_node_id not in node_ids:
                errors.append(f"Edge target node ID '{edge.target_node_id}' does not exist")

        if not agent.entry_node:
            warnings.append("No entry node set — will execute nodes in creation order")

        return GraphValidationReport(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            node_count=len(nodes),
            edge_count=len(edges),
        )
