import enum


class AgentStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class NodeType(str, enum.Enum):
    functional = "functional"
    llm_call = "llm_call"


class NodeSubtype(str, enum.Enum):
    python_inline = "python_inline"
    api_call = "api_call"
    agent_call = "agent_call"
    chat = "chat"


class NodeCategory(str, enum.Enum):
    functional = "functional"
    llm = "llm"


class AgentCallInputMode(str, enum.Enum):
    entire_state = "entire_state"
    state_key = "state_key"
    template = "template"


class AgentCallOutputMode(str, enum.Enum):
    merge_state = "merge_state"
    write_to_key = "write_to_key"


class EdgeType(str, enum.Enum):
    direct = "direct"
    conditional = "conditional"


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
