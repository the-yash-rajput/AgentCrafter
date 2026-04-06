from __future__ import annotations

import json
from typing import Any, Optional

from jinja2 import Template
from models import AgentCallInputMode, AgentCallOutputMode
from type_defs import ExecutionContext, JSONMapping, NodeRunner, StatePayload


def build_agent_call_node(
    config: JSONMapping,
    *,
    db=None,
    current_agent_id: Optional[int] = None,
    execution_context: Optional[ExecutionContext] = None,
) -> NodeRunner:
    agent_cfg = config.get("agent_call", {})

    def agent_call_node(state: StatePayload) -> StatePayload:
        target_agent_id = agent_cfg.get("target_agent_id")
        target_agent_name = str(agent_cfg.get("target_agent_name") or "").strip()
        input_key = str(agent_cfg.get("input_key") or "").strip()
        input_template = str(agent_cfg.get("input_template") or "").strip()
        output_key = str(agent_cfg.get("output_key") or "agent_result").strip() or "agent_result"
        include_run_metadata = bool(agent_cfg.get("include_run_metadata", False))

        if db is None:
            return {**state, "_error": "Agent Call nodes require a database session"}

        try:
            input_mode = AgentCallInputMode(
                str(agent_cfg.get("input_mode", AgentCallInputMode.entire_state.value))
            )
            output_mode = AgentCallOutputMode(
                str(agent_cfg.get("output_mode", AgentCallOutputMode.merge_state.value))
            )
        except ValueError as exc:
            return {**state, "_error": str(exc)}

        from models import Agent
        from runtime.graph_runner import GraphRunner

        target_agent = None
        if target_agent_id not in (None, ""):
            try:
                target_agent = db.query(Agent).filter(Agent.id == int(target_agent_id)).first()
            except (TypeError, ValueError):
                return {**state, "_error": f"Invalid target agent ID '{target_agent_id}'"}
        elif target_agent_name:
            target_agent = db.query(Agent).filter(Agent.name == target_agent_name).first()
        else:
            return {**state, "_error": "Agent Call node requires target_agent_id or target_agent_name"}

        if not target_agent:
            target_label = target_agent_name or target_agent_id
            return {**state, "_error": f"Target agent '{target_label}' not found"}

        if current_agent_id is not None and target_agent.id == current_agent_id:
            return {**state, "_error": "Agent Call node cannot target the same agent"}

        nested_input: Any
        if input_mode == AgentCallInputMode.state_key:
            if not input_key:
                return {**state, "_error": "Agent Call node requires input_key for state_key mode"}
            nested_input = state.get(input_key, {})
        elif input_mode == AgentCallInputMode.template:
            if not input_template:
                return {**state, "_error": "Agent Call node requires input_template for template mode"}
            try:
                rendered = Template(input_template).render(**state)
                nested_input = json.loads(rendered)
            except Exception as exc:
                return {**state, "_error": f"Failed to render agent input template: {exc}"}
        else:
            nested_input = dict(state)

        if not isinstance(nested_input, dict):
            return {**state, "_error": "Agent Call node input must resolve to a JSON object"}

        try:
            result = GraphRunner(db).compile_and_run(
                target_agent.id,
                nested_input,
                execution_context=execution_context,
            )
        except Exception as exc:
            return {**state, "_error": str(exc)}

        child_output = result.get("output", {})
        if not isinstance(child_output, dict):
            child_output = {output_key: child_output}

        if output_mode == AgentCallOutputMode.write_to_key:
            next_state = {**state, output_key: child_output}
        else:
            next_state = child_output

        if include_run_metadata:
            next_state = {
                **next_state,
                f"{output_key}_meta": {
                    "target_agent_id": target_agent.id,
                    "target_agent_name": target_agent.name,
                    "run_id": result.get("run_id"),
                    "status": result.get("status"),
                },
            }

        return next_state

    return agent_call_node
