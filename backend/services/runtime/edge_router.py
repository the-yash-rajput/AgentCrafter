from typing import Callable


def build_condition_router(condition_config: dict, edges: list) -> Callable:
    """Build a routing function for conditional edges."""
    condition_type = condition_config.get("condition_type", "state_key_equals")

    def router(state: dict) -> str:
        if condition_type == "state_key_equals":
            cfg = condition_config.get("state_key_equals", {})
            key = cfg.get("key", "")
            state_val = state.get(key, "")
            for edge in edges:
                if edge.get("label") == str(state_val) or edge.get("target") == str(state_val):
                    return edge.get("target")
            return edges[0].get("target") if edges else "__end__"

        if condition_type == "python_expression":
            cfg = condition_config.get("python_expression", {})
            expression = cfg.get("expression", "True")
            try:
                result = eval(expression, {"state": state})
                if result and len(edges) > 0:
                    return edges[0].get("target")
                if not result and len(edges) > 1:
                    return edges[1].get("target")
            except Exception:
                pass
            return edges[0].get("target") if edges else "__end__"

        if condition_type == "llm_router":
            cfg = condition_config.get("llm_router", {})
            routing_key = cfg.get("routing_key", "next_step")
            routing_value = state.get(routing_key, "")
            for edge in edges:
                if edge.get("label") == str(routing_value):
                    return edge.get("target")
            return edges[0].get("target") if edges else "__end__"

        return edges[0].get("target") if edges else "__end__"

    return router
