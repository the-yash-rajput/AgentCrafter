import enum


class AgentStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class NodeType(str, enum.Enum):
    functional = "functional"
    llm_call = "llm_call"


class EdgeType(str, enum.Enum):
    direct = "direct"
    conditional = "conditional"


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
