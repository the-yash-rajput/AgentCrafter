from __future__ import annotations

from typing import Any, Optional

from services.node_definition import resolve_node_definition
from models import NodeSubtype, NodeType
from type_defs import ExecutionContext, JSONMapping, NodeRunner


class NodeRunnerFactory:
    def build(
        self,
        *,
        node_type: NodeType | str,
        subtype: NodeSubtype | str | None = None,
        config: Optional[JSONMapping] = None,
        db=None,
        current_agent_id: Optional[int] = None,
        execution_context: Optional[ExecutionContext] = None,
        agent_name: Optional[str] = None,
        run_id: Optional[str] = None,
        node_name: Optional[str] = None,
    ) -> NodeRunner:
        resolved_type, resolved_subtype, resolved_config = resolve_node_definition(
            node_type,
            subtype,
            config,
        )

        if resolved_type == NodeType.functional:
            from services.runtime.nodes.types.functional import build_functional_node

            return build_functional_node(
                resolved_subtype,
                resolved_config,
                db=db,
                current_agent_id=current_agent_id,
                execution_context=execution_context,
            )

        if resolved_type == NodeType.llm_call:
            from services.runtime.nodes.types.llm import build_llm_node

            return build_llm_node(
                resolved_subtype,
                resolved_config,
                execution_context=execution_context,
                agent_name=agent_name,
                run_id=run_id,
                node_name=node_name,
            )

        if resolved_type == NodeType.communication:
            from services.runtime.nodes.types.communication import build_communication_node

            return build_communication_node(
                resolved_subtype,
                resolved_config,
            )

        raise ValueError(f"No runner registered for node type '{resolved_type.value}'")


def build_node_runner(**kwargs) -> NodeRunner:
    return NodeRunnerFactory().build(**kwargs)
