from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Any, List
from datetime import datetime
from models import AgentStatus, NodeCategory, NodeSubtype, NodeType, EdgeType, RunStatus
from services.node_definition import normalize_node_subtype, normalize_node_type, resolve_node_definition
from type_defs import JSONMapping


# ─── Agent Schemas ───────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    state_schema: JSONMapping = Field(default_factory=dict)
    entry_node: Optional[str] = None
    exit_nodes: List[str] = Field(default_factory=list)
    metadata_: JSONMapping = Field(default_factory=dict, alias="metadata")

    class Config:
        populate_by_name = True


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[AgentStatus] = None
    state_schema: Optional[JSONMapping] = None
    entry_node: Optional[str] = None
    exit_nodes: Optional[List[str]] = None
    metadata_: Optional[JSONMapping] = Field(default=None, alias="metadata")

    class Config:
        populate_by_name = True


class AgentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    status: AgentStatus
    state_schema: JSONMapping
    entry_node: Optional[str]
    exit_nodes: List[str] = Field(default_factory=list)
    metadata: JSONMapping = Field(default_factory=dict, alias="metadata_")
    versions: List["AgentVersionResponse"] = Field(default_factory=list)
    agent_version_id: Optional[int] = None
    version_number: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class AgentWithGraph(AgentResponse):
    nodes: List["NodeResponse"] = Field(default_factory=list)
    edges: List["EdgeResponse"] = Field(default_factory=list)


class AgentVersionCreate(BaseModel):
    base_version_id: Optional[int] = None


class AgentVersionUpdate(BaseModel):
    state_schema: Optional[JSONMapping] = None
    entry_node: Optional[str] = None
    exit_nodes: Optional[List[str]] = None
    metadata_: Optional[JSONMapping] = Field(default=None, alias="metadata")

    class Config:
        populate_by_name = True


class AgentVersionResponse(BaseModel):
    id: int
    agent_id: int
    version_number: int
    base_version_id: Optional[int] = None
    state_schema: JSONMapping
    entry_node: Optional[str]
    exit_nodes: List[str] = Field(default_factory=list)
    metadata: JSONMapping = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class AgentVersionWithGraph(AgentVersionResponse):
    agent: AgentResponse
    nodes: List["NodeResponse"] = Field(default_factory=list)
    edges: List["EdgeResponse"] = Field(default_factory=list)


# ─── Node Schemas ─────────────────────────────────────────────────────────────

class NodeCreate(BaseModel):
    name: str
    type: NodeType
    subtype: Optional[NodeSubtype] = None
    config: JSONMapping = Field(default_factory=dict)
    position_x: float = 0.0
    position_y: float = 0.0

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, value):
        return normalize_node_type(value)

    @field_validator("subtype", mode="before")
    @classmethod
    def validate_subtype(cls, value):
        return normalize_node_subtype(value)

    @model_validator(mode="after")
    def sync_subtype_and_config(self):
        self.type, self.subtype, self.config = resolve_node_definition(
            self.type,
            self.subtype,
            self.config,
        )
        return self


class NodeUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[NodeType] = None
    subtype: Optional[NodeSubtype] = None
    config: Optional[JSONMapping] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, value):
        if value is None:
            return value
        return normalize_node_type(value)

    @field_validator("subtype", mode="before")
    @classmethod
    def validate_subtype(cls, value):
        return normalize_node_subtype(value)


class NodeResponse(BaseModel):
    id: int
    agent_id: int
    agent_version_id: Optional[int] = None
    name: str
    type: NodeType
    subtype: NodeSubtype
    config: JSONMapping
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
    condition_config: JSONMapping = Field(default_factory=dict)
    label: Optional[str] = None


class EdgeUpdate(BaseModel):
    source_node_id: Optional[int] = None
    target_node_id: Optional[int] = None
    edge_type: Optional[EdgeType] = None
    condition_config: Optional[JSONMapping] = None
    label: Optional[str] = None


class EdgeResponse(BaseModel):
    id: int
    agent_id: int
    agent_version_id: Optional[int] = None
    source_node_id: int
    target_node_id: int
    edge_type: EdgeType
    condition_config: JSONMapping
    label: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Run Schemas ──────────────────────────────────────────────────────────────

class RunCreate(BaseModel):
    input_data: JSONMapping = Field(default_factory=dict)
    session_id: Optional[int] = None

    @field_validator("session_id")
    @classmethod
    def normalize_session_id(cls, value):
        if value is None:
            return None

        try:
            normalized = int(value)
        except (TypeError, ValueError):
            raise ValueError("session_id must be an integer") from None

        return normalized if normalized > 0 else None


class RunResponse(BaseModel):
    id: int
    agent_id: int
    agent_version_id: Optional[int] = None
    session_id: Optional[int]
    parent_run_id: Optional[int] = None
    status: RunStatus
    input_data: JSONMapping
    output_data: JSONMapping
    conversation_history: Any = Field(default_factory=list)
    conversation_turn: Any = Field(default_factory=list)
    state_snapshots: Any
    error: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class AgentSessionCreate(BaseModel):
    metadata_: JSONMapping = Field(default_factory=dict, alias="metadata")

    class Config:
        populate_by_name = True


class AgentSessionResponse(BaseModel):
    id: int
    agent_id: int
    agent_version_id: int
    conversation_history: Any = Field(default_factory=list)
    metadata: JSONMapping = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime
    last_run_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        populate_by_name = True


class NodeDefinitionResponse(BaseModel):
    type: NodeType
    subtype: NodeSubtype
    category: NodeCategory
    label: str
    description: str
    show_in_frontend: bool
    default_config: JSONMapping

    class Config:
        from_attributes = True


AgentResponse.model_rebuild()
AgentWithGraph.model_rebuild()
AgentVersionWithGraph.model_rebuild()
