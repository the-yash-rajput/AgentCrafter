from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from type_defs import ExecutionContext, JSONMapping, NodeRunner

if TYPE_CHECKING:
    from models import NodeSubtype


def build_llm_node(
    subtype: "NodeSubtype | str",
    config: JSONMapping,
    *,
    execution_context: Optional[ExecutionContext] = None,
    agent_name: Optional[str] = None,
    run_id: Optional[str] = None,
    node_name: Optional[str] = None,
) -> NodeRunner:
    resolved_subtype = getattr(subtype, "value", subtype)
    legacy_runtime = str(config.get("llm_runtime") or "").strip().lower()
    if str(resolved_subtype) == "llm_agent" or legacy_runtime == "agent":
        from services.runtime.nodes.types.llm.agent import build_agent_llm_node

        return build_agent_llm_node(
            config,
            execution_context=execution_context,
            agent_name=agent_name,
            run_id=run_id,
            node_name=node_name,
        )

    if str(resolved_subtype) == "chat":
        from services.runtime.nodes.types.llm.chat import build_chat_llm_node

        return build_chat_llm_node(
            config,
            execution_context=execution_context,
            agent_name=agent_name,
            run_id=run_id,
            node_name=node_name,
        )

    raise ValueError(f"Unsupported llm node subtype '{subtype}'")
