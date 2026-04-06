from __future__ import annotations

from task_runner import PythonTaskConfig, PythonTaskRunner
from type_defs import JSONMapping, NodeRunner, StatePayload


def build_python_inline_node(config: JSONMapping) -> NodeRunner:
    inline_config = config.get("python_inline", {})
    code = inline_config.get("code", "def run(state):\n    return state")
    task_runner = PythonTaskRunner()
    task_config = PythonTaskConfig.from_inline_config(inline_config)

    def functional_node(state: StatePayload) -> StatePayload:
        try:
            result = task_runner.run(code=code, state=state, config=task_config)
            return result.output
        except Exception as exc:
            return {**state, "_error": str(exc)}

    return functional_node
