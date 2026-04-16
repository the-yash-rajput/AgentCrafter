from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from models.enums import AgentCallInputMode, AgentCallOutputMode, NodeCategory, NodeSubtype, NodeType
from type_defs import JSONMapping


FUNCTIONAL_NODE_SUBTYPES = {
    NodeSubtype.python_inline,
    NodeSubtype.agent_call,
}
LLM_NODE_SUBTYPES = {
    NodeSubtype.chat,
    NodeSubtype.llm_agent,
}
COMMUNICATION_NODE_SUBTYPES = {
    NodeSubtype.rabbitmq_message,
    NodeSubtype.kafka,
    NodeSubtype.api,
}
DEFAULT_NODE_SUBTYPE_BY_TYPE = {
    NodeType.functional: NodeSubtype.python_inline,
    NodeType.llm_call: NodeSubtype.chat,
    NodeType.communication: NodeSubtype.rabbitmq_message,
}
NODE_TYPE_ALIASES = {
    "functional": NodeType.functional,
    "llm": NodeType.llm_call,
    "llm_call": NodeType.llm_call,
    "communication": NodeType.communication,
}
NODE_SUBTYPES_BY_TYPE = {
    NodeType.functional: FUNCTIONAL_NODE_SUBTYPES,
    NodeType.llm_call: LLM_NODE_SUBTYPES,
    NodeType.communication: COMMUNICATION_NODE_SUBTYPES,
}


@dataclass(frozen=True)
class NodeDefinitionSpec:
    type: NodeType
    subtype: NodeSubtype
    category: NodeCategory
    label: str
    description: str
    show_in_frontend: bool
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
    return config


def _build_default_communication_config(subtype: NodeSubtype) -> JSONMapping:
    config: JSONMapping = {
        "node_type": NodeType.communication.value,
        "communication_type": subtype.value,
        "rabbitmq_message": {
            "host": "localhost",
            "port": 5672,
            "exchange": "",
            "routing_key": "",
            "queue": "",
            "payload_template": "{\"input\": {{input | tojson}}}",
            "output_key": "rabbitmq_result",
        },
        "kafka": {
            "bootstrap_servers": "localhost:9092",
            "topic": "",
            "key_template": "",
            "payload_template": "{\"input\": {{input | tojson}}}",
            "output_key": "kafka_result",
        },
        "api": {
            "url": "",
            "method": "POST",
            "headers": {},
            "body_template": "{\"input\": {{input | tojson}}}",
            "output_key": "api_result",
        },
    }
    return config


def _build_default_llm_config(subtype: NodeSubtype) -> JSONMapping:
    return {
        "node_type": NodeType.llm_call.value,
        "llm_type": subtype.value,
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
    }


NODE_DEFINITIONS = (
    NodeDefinitionSpec(
        type=NodeType.llm_call,
        subtype=NodeSubtype.chat,
        category=NodeCategory.llm,
        label="LLM Call",
        description="Call Azure OpenAI, Anthropic, or other LLMs directly",
        show_in_frontend=True,
        default_config=_build_default_llm_config(NodeSubtype.chat),
    ),
    NodeDefinitionSpec(
        type=NodeType.llm_call,
        subtype=NodeSubtype.llm_agent,
        category=NodeCategory.llm,
        label="LLM Agent",
        description="Run a LangChain agent with middleware-based model and tool control",
        show_in_frontend=True,
        default_config=_build_default_llm_config(NodeSubtype.llm_agent),
    ),
    NodeDefinitionSpec(
        type=NodeType.functional,
        subtype=NodeSubtype.python_inline,
        category=NodeCategory.functional,
        label="Python Function",
        description="Run inline Python code",
        show_in_frontend=True,
        default_config=_build_default_functional_config(NodeSubtype.python_inline),
    ),
    NodeDefinitionSpec(
        type=NodeType.functional,
        subtype=NodeSubtype.agent_call,
        category=NodeCategory.functional,
        label="Agent Call",
        description="Hand off state to another agent in the workspace",
        show_in_frontend=True,
        default_config=_build_default_functional_config(NodeSubtype.agent_call),
    ),
    NodeDefinitionSpec(
        type=NodeType.communication,
        subtype=NodeSubtype.rabbitmq_message,
        category=NodeCategory.communication,
        label="RabbitMQ Message",
        description="Publish a message to RabbitMQ",
        show_in_frontend=True,
        default_config=_build_default_communication_config(NodeSubtype.rabbitmq_message),
    ),
    NodeDefinitionSpec(
        type=NodeType.communication,
        subtype=NodeSubtype.kafka,
        category=NodeCategory.communication,
        label="Kafka",
        description="Publish a message to Kafka",
        show_in_frontend=False,
        default_config=_build_default_communication_config(NodeSubtype.kafka),
    ),
    NodeDefinitionSpec(
        type=NodeType.communication,
        subtype=NodeSubtype.api,
        category=NodeCategory.communication,
        label="API",
        description="Send a communication request to an HTTP endpoint",
        show_in_frontend=True,
        default_config=_build_default_communication_config(NodeSubtype.api),
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
        elif normalized_type == NodeType.llm_call:
            normalized_subtype = normalize_node_subtype(normalized_config.get("llm_type"))
        elif normalized_type == NodeType.communication:
            normalized_subtype = normalize_node_subtype(normalized_config.get("communication_type"))
        normalized_subtype = normalized_subtype or DEFAULT_NODE_SUBTYPE_BY_TYPE[normalized_type]

    legacy_llm_runtime = str(normalized_config.get("llm_runtime") or "").strip().lower()
    if normalized_type == NodeType.llm_call and legacy_llm_runtime == "agent":
        normalized_subtype = NodeSubtype.llm_agent

    if normalized_type == NodeType.functional and normalized_subtype == NodeSubtype.api_call:
        normalized_type = NodeType.communication
        normalized_subtype = NodeSubtype.api
        normalized_config = {
            **normalized_config,
            "node_type": NodeType.communication.value,
            "communication_type": NodeSubtype.api.value,
            "api": deepcopy(
                normalized_config.get("api")
                or normalized_config.get("api_call")
                or _build_default_communication_config(NodeSubtype.api).get("api", {})
            ),
        }

    supported_subtypes = NODE_SUBTYPES_BY_TYPE.get(normalized_type, set())
    if normalized_subtype not in supported_subtypes:
        raise ValueError(
            f"Unsupported subtype '{normalized_subtype}' for node type '{normalized_type.value}'"
        )

    if normalized_type == NodeType.functional:
        normalized_config["function_type"] = normalized_subtype.value
    if normalized_type == NodeType.llm_call:
        normalized_config["llm_type"] = normalized_subtype.value
        normalized_config.pop("llm_runtime", None)
    if normalized_type == NodeType.communication:
        normalized_config["communication_type"] = normalized_subtype.value

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
            show_in_frontend=definition.show_in_frontend,
            default_config=deepcopy(definition.default_config),
        ))
    return definitions
