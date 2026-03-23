from pydantic import BaseModel, Field
from typing import Optional, Any, List
from datetime import datetime
from models import AgentStatus, NodeType, EdgeType, RunStatus


# ─── Agent Schemas ───────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)
    state_schema: dict = Field(default_factory=dict)
    entry_node: Optional[str] = None
    exit_node: Optional[str] = None
    exit_nodes: List[str] = Field(default_factory=list)
    metadata_: dict = Field(default_factory=dict, alias="metadata")

    class Config:
        populate_by_name = True


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[AgentStatus] = None
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None
    state_schema: Optional[dict] = None
    entry_node: Optional[str] = None
    exit_node: Optional[str] = None
    exit_nodes: Optional[List[str]] = None
    metadata_: Optional[dict] = Field(default=None, alias="metadata")

    class Config:
        populate_by_name = True


class AgentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    status: AgentStatus
    input_schema: dict
    output_schema: dict
    state_schema: dict
    entry_node: Optional[str]
    exit_node: Optional[str]
    exit_nodes: List[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class AgentWithGraph(AgentResponse):
    nodes: List["NodeResponse"] = Field(default_factory=list)
    edges: List["EdgeResponse"] = Field(default_factory=list)


# ─── Node Schemas ─────────────────────────────────────────────────────────────

class NodeCreate(BaseModel):
    name: str
    type: NodeType
    config: dict = Field(default_factory=dict)
    position_x: float = 0.0
    position_y: float = 0.0


class NodeUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None


class NodeResponse(BaseModel):
    id: int
    agent_id: int
    name: str
    type: NodeType
    config: dict
    position_x: float
    position_y: float
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Edge Schemas ─────────────────────────────────────────────────────────────

class EdgeCreate(BaseModel):
    source_node_id: int
    target_node_id: int
    edge_type: EdgeType = EdgeType.direct
    condition_config: dict = Field(default_factory=dict)
    label: Optional[str] = None


class EdgeUpdate(BaseModel):
    source_node_id: Optional[int] = None
    target_node_id: Optional[int] = None
    edge_type: Optional[EdgeType] = None
    condition_config: Optional[dict] = None
    label: Optional[str] = None


class EdgeResponse(BaseModel):
    id: int
    agent_id: int
    source_node_id: int
    target_node_id: int
    edge_type: EdgeType
    condition_config: dict
    label: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Run Schemas ──────────────────────────────────────────────────────────────

class RunCreate(BaseModel):
    input_data: dict = Field(default_factory=dict)


class RunResponse(BaseModel):
    id: int
    agent_id: int
    status: RunStatus
    input_data: dict
    output_data: dict
    state_snapshots: Any
    error: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


AgentWithGraph.model_rebuild()
