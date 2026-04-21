from typing import Callable, List, Union


def _match_state_key_equals(
    condition_config: dict, edges: list, state: dict
) -> Union[str, List[str]]:
    """
    Route by comparing state[key] against each edge's configured `condition_value`.

    - The shared condition_config supplies the state key to read (e.g. "ownership_result").
    - Each edge in `edges` carries its own `condition_value` (populated by builder.py
      from condition_config.state_key_equals.value on that specific edge).
    - Comparison is case-insensitive string equality, so boolean state values
      (True/False) match UI-entered "true"/"false"/"True" strings.
    - Exactly one match  → return that target (string).
    - Two or more matches → return the list of matching targets; LangGraph will
      branch to all of them in parallel.
    - No match           → fall back to the first edge's target.
    """
    cfg = condition_config.get("state_key_equals", {})
    key = cfg.get("key", "")
    state_val = str(state.get(key, "")).lower()

    matched = [
        edge.get("target")
        for edge in edges
        if str(edge.get("condition_value", "")).lower() == state_val
    ]

    if len(matched) == 1:
        return matched[0]
    if len(matched) > 1:
        return matched
    return edges[0].get("target") if edges else "__end__"


def _match_python_expression(
    condition_config: dict, edges: list, state: dict
) -> str:
    """
    Evaluate the configured Python expression against the state dict.

    Truthy  → edges[0].target  (the "yes" branch)
    Falsy   → edges[1].target  (the "no" branch, if declared)
    Error / no edges → fall back to edges[0].target or "__end__"

    Only the first edge's condition_config is used (see builder.py); all
    sibling edges share this same expression and are distinguished by order.
    """
    cfg = condition_config.get("python_expression", {})
    expression = cfg.get("expression", "True")
    try:
        result = eval(expression, {"state": state})
    except Exception:
        return edges[0].get("target") if edges else "__end__"

    if result and edges:
        return edges[0].get("target")
    if not result and len(edges) > 1:
        return edges[1].get("target")
    return edges[0].get("target") if edges else "__end__"


def _match_llm_router(
    condition_config: dict, edges: list, state: dict
) -> str:
    """
    Route using a key an upstream LLM wrote into state (e.g. state["next_step"]).

    The string value at state[routing_key] is matched against edge labels —
    intentionally label-based because the LLM is expected to emit one of the
    pre-declared branch labels verbatim.
    
    TODO: Think more and test around how to handle mismatches (e.g. due to LLM typos or unexpected values).
    """
    cfg = condition_config.get("llm_router", {})
    routing_key = cfg.get("routing_key", "next_step")
    routing_value = str(state.get(routing_key, ""))
    for edge in edges:
        if edge.get("label") == routing_value:
            return edge.get("target")
    return edges[0].get("target") if edges else "__end__"


_HANDLERS = {
    "state_key_equals": _match_state_key_equals,
    "python_expression": _match_python_expression,
    "llm_router": _match_llm_router,
}


def build_condition_router(condition_config: dict, edges: list) -> Callable:
    """Return a routing function closing over the given condition_config + edges."""
    condition_type = condition_config.get("condition_type", "state_key_equals")
    handler = _HANDLERS.get(condition_type)

    def router(state: dict):
        if handler is None:
            return edges[0].get("target") if edges else "__end__"
        return handler(condition_config, edges, state)

    return router
