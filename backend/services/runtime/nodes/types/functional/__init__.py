from __future__ import annotations

from typing import Optional

from models import NodeSubtype
from type_defs import ExecutionContext, JSONMapping, NodeRunner


def build_functional_node(
    subtype: NodeSubtype,
    config: JSONMapping,
    *,
    db=None,
    current_agent_id: Optional[int] = None,
    execution_context: Optional[ExecutionContext] = None,
) -> NodeRunner:
    if subtype == NodeSubtype.python_inline:
        from services.runtime.nodes.types.functional.python_inline import build_python_inline_node

        return build_python_inline_node(config)

    if subtype == NodeSubtype.agent_call:
        from services.runtime.nodes.types.functional.agent_call import build_agent_call_node

        return build_agent_call_node(
            config,
            db=db,
            current_agent_id=current_agent_id,
            execution_context=execution_context,
        )

    raise ValueError(f"Unsupported functional node subtype '{subtype}'")
