from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from models.enums import AgentCallInputMode, AgentCallOutputMode, NodeCategory, NodeSubtype, NodeType
from type_defs import JSONMapping


FUNCTIONAL_NODE_SUBTYPES = {
    NodeSubtype.python_inline,
    NodeSubtype.api_call,
    NodeSubtype.agent_call,
}
LLM_NODE_SUBTYPES = {
    NodeSubtype.chat,
}
DEFAULT_NODE_SUBTYPE_BY_TYPE = {
    NodeType.functional: NodeSubtype.python_inline,
    NodeType.llm_call: NodeSubtype.chat,
}
NODE_TYPE_ALIASES = {
    "functional": NodeType.functional,
    "llm": NodeType.llm_call,
    "llm_call": NodeType.llm_call,
}
NODE_SUBTYPES_BY_TYPE = {
    NodeType.functional: FUNCTIONAL_NODE_SUBTYPES,
    NodeType.llm_call: LLM_NODE_SUBTYPES,
}


@dataclass(frozen=True)
class NodeDefinitionSpec:
    type: NodeType
    subtype: NodeSubtype
    category: NodeCategory
    label: str
    description: str
    default_config: JSONMapping


def _build_agent_call_default_config() -> JSONMapping:
    return {
        "target_agent_id": "",
        "target_agent_name": "",
        "input_mode": AgentCallInputMode.entire_state.value,
        "input_key": "",
        "input_template": "{\n  \"input\": \"{{input}}\"\n}",
        "output_mode": AgentCallOutputMode.merge_state.value,
        "output_key": "agent_result",
        "include_run_metadata": True,
    }


def _build_default_functional_config(subtype: NodeSubtype) -> JSONMapping:
    config: JSONMapping = {
        "node_type": NodeType.functional.value,
        "function_type": subtype.value,
        "python_inline": {
            "code": "def run(state):\n    return state",
        },
        "agent_call": _build_agent_call_default_config(),
    }
    if subtype == NodeSubtype.api_call:
        config["api_call"] = {
            "url": "",
            "method": "GET",
            "headers": {},
            "body_template": "",
            "output_key": "api_result",
        }
    return config


NODE_DEFINITIONS = (
    NodeDefinitionSpec(
        type=NodeType.llm_call,
        subtype=NodeSubtype.chat,
        category=NodeCategory.llm,
        label="LLM Call",
        description="Call Azure OpenAI, Anthropic, or other LLMs",
        default_config={
            "node_type": NodeType.llm_call.value,
            "provider": "azure_openai",
            "model": "ai-agent-4o",
            "api_key_env_var": "AZURE_OPENAI_API_KEY",
            "use_langfuse_prompt": False,
            "langfuse_prompt_name": "",
            "system_prompt": "You are a helpful assistant.",
            "user_prompt_template": "{{input}}",
            "temperature": 0.7,
            "max_tokens": 1000,
            "output_key": "llm_response",
        },
    ),
    NodeDefinitionSpec(
        type=NodeType.functional,
        subtype=NodeSubtype.python_inline,
        category=NodeCategory.functional,
        label="Python Function",
        description="Run inline Python code",
        default_config=_build_default_functional_config(NodeSubtype.python_inline),
    ),
    NodeDefinitionSpec(
        type=NodeType.functional,
        subtype=NodeSubtype.api_call,
        category=NodeCategory.functional,
        label="API Call",
        description="HTTP GET/POST to external APIs",
        default_config=_build_default_functional_config(NodeSubtype.api_call),
    ),
    NodeDefinitionSpec(
        type=NodeType.functional,
        subtype=NodeSubtype.agent_call,
        category=NodeCategory.functional,
        label="Agent Call",
        description="Hand off state to another agent in the workspace",
        default_config=_build_default_functional_config(NodeSubtype.agent_call),
    ),
)


def normalize_node_type(value: Any) -> NodeType:
    if isinstance(value, NodeType):
        return value

    key = str(value or "").strip().lower()
    if key in NODE_TYPE_ALIASES:
        return NODE_TYPE_ALIASES[key]

    raise ValueError(f"Unsupported node type '{value}'")


def normalize_node_subtype(value: Any) -> NodeSubtype | None:
    if value in (None, ""):
        return None
    if isinstance(value, NodeSubtype):
        return value
    return NodeSubtype(str(value).strip().lower())


def resolve_node_definition(
    node_type: Any,
    subtype: Any = None,
    config: JSONMapping | None = None,
) -> tuple[NodeType, NodeSubtype, JSONMapping]:
    normalized_type = normalize_node_type(node_type)
    normalized_config = deepcopy(config or {})
    normalized_subtype = normalize_node_subtype(subtype)

    if not normalized_subtype:
        if normalized_type == NodeType.functional:
            normalized_subtype = normalize_node_subtype(normalized_config.get("function_type"))
        normalized_subtype = normalized_subtype or DEFAULT_NODE_SUBTYPE_BY_TYPE[normalized_type]

    supported_subtypes = NODE_SUBTYPES_BY_TYPE.get(normalized_type, set())
    if normalized_subtype not in supported_subtypes:
        raise ValueError(
            f"Unsupported subtype '{normalized_subtype}' for node type '{normalized_type.value}'"
        )

    if normalized_type == NodeType.functional:
        normalized_config["function_type"] = normalized_subtype.value

    return normalized_type, normalized_subtype, normalized_config


def get_node_definitions() -> list[NodeDefinitionSpec]:
    definitions: list[NodeDefinitionSpec] = []
    for definition in NODE_DEFINITIONS:
        definitions.append(NodeDefinitionSpec(
            type=definition.type,
            subtype=definition.subtype,
            category=definition.category,
            label=definition.label,
            description=definition.description,
            default_config=deepcopy(definition.default_config),
        ))
    return definitions
