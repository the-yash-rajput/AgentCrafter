from __future__ import annotations

from typing import Optional

from models import NodeSubtype
from type_defs import ExecutionContext, JSONMapping, NodeRunner

def build_llm_node(
    subtype: NodeSubtype,
    config: JSONMapping,
    *,
    execution_context: Optional[ExecutionContext] = None,
    agent_name: Optional[str] = None,
    run_id: Optional[str] = None,
    node_name: Optional[str] = None,
) -> NodeRunner:
    if subtype != NodeSubtype.chat:
        raise ValueError(f"Unsupported llm node subtype '{subtype}'")

    from services.runtime.nodes.types.llm.chat import build_chat_llm_node

    return build_chat_llm_node(
        config,
        execution_context=execution_context,
        agent_name=agent_name,
        run_id=run_id,
        node_name=node_name,
    )
