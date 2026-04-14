from models.enums import (
    AgentCallInputMode,
    AgentCallOutputMode,
    AgentStatus,
    EdgeType,
    NodeCategory,
    NodeSubtype,
    NodeType,
    RunStatus,
)

__all__ = [
    "AgentStatus",
    "AgentCallInputMode",
    "AgentCallOutputMode",
    "NodeType",
    "NodeSubtype",
    "NodeCategory",
    "EdgeType",
    "RunStatus",
    "Agent",
    "AgentVersion",
    "AgentSession",
    "Node",
    "Edge",
    "Run",
]


def __getattr__(name: str):
    if name == "Agent":
        from models.agent import Agent
        return Agent
    if name == "AgentVersion":
        from models.agent_version import AgentVersion
        return AgentVersion
    if name == "AgentSession":
        from models.agent_session import AgentSession
        return AgentSession
    if name == "Node":
        from models.node import Node
        return Node
    if name == "Edge":
        from models.edge import Edge
        return Edge
    if name == "Run":
        from models.run import Run
        return Run
    raise AttributeError(f"module 'models' has no attribute '{name}'")
