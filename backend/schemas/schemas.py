from pydantic import BaseModel, Field
from typing import Optional, Any, List
from uuid import UUID
from datetime import datetime
from models.models import AgentStatus, NodeType, EdgeType, RunStatus


# ─── Agent Schemas ───────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    input_schema: Optional[dict] = {}
    output_schema: Optional[dict] = {}
    state_schema: Optional[dict] = {}
    entry_node: Optional[str] = None
    exit_node: Optional[str] = None
    metadata_: Optional[dict] = Field(default={}, alias="metadata")

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
    metadata_: Optional[dict] = Field(default=None, alias="metadata")

    class Config:
        populate_by_name = True


class AgentResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    status: AgentStatus
    input_schema: dict
    output_schema: dict
    state_schema: dict
    entry_node: Optional[str]
    exit_node: Optional[str]
    metadata: dict = Field(default={}, alias="metadata_")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class AgentWithGraph(AgentResponse):
    nodes: List["NodeResponse"] = []
    edges: List["EdgeResponse"] = []


# ─── Node Schemas ─────────────────────────────────────────────────────────────

class NodeCreate(BaseModel):
    name: str
    type: NodeType
    config: Optional[dict] = {}
    position_x: Optional[float] = 0.0
    position_y: Optional[float] = 0.0


class NodeUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None


class NodeResponse(BaseModel):
    id: UUID
    agent_id: UUID
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
    source_node_id: str
    target_node_id: str
    edge_type: EdgeType = EdgeType.direct
    condition_config: Optional[dict] = {}
    label: Optional[str] = None


class EdgeUpdate(BaseModel):
    edge_type: Optional[EdgeType] = None
    condition_config: Optional[dict] = None
    label: Optional[str] = None


class EdgeResponse(BaseModel):
    id: UUID
    agent_id: UUID
    source_node_id: str
    target_node_id: str
    edge_type: EdgeType
    condition_config: dict
    label: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Run Schemas ──────────────────────────────────────────────────────────────

class RunCreate(BaseModel):
    input_data: dict = {}


class RunResponse(BaseModel):
    id: UUID
    agent_id: UUID
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
