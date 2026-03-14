import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from db.base import Base
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


class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(AgentStatus), default=AgentStatus.draft, nullable=False)
    input_schema = Column(JSONB, default=dict)
    output_schema = Column(JSONB, default=dict)
    state_schema = Column(JSONB, default=dict)
    entry_node = Column(String(255), nullable=True)
    exit_node = Column(String(255), nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    nodes = relationship("Node", back_populates="agent", cascade="all, delete-orphan")
    edges = relationship("Edge", back_populates="agent", cascade="all, delete-orphan")
    runs = relationship("Run", back_populates="agent", cascade="all, delete-orphan")


class Node(Base):
    __tablename__ = "nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(SAEnum(NodeType), nullable=False)
    config = Column(JSONB, default=dict)
    position_x = Column(Float, default=0.0)
    position_y = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("Agent", back_populates="nodes")


class Edge(Base):
    __tablename__ = "edges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    source_node_id = Column(String(255), nullable=False)
    target_node_id = Column(String(255), nullable=False)
    edge_type = Column(SAEnum(EdgeType), default=EdgeType.direct, nullable=False)
    condition_config = Column(JSONB, default=dict)
    label = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("Agent", back_populates="edges")


class Run(Base):
    __tablename__ = "runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    status = Column(SAEnum(RunStatus), default=RunStatus.pending, nullable=False)
    input_data = Column(JSONB, default=dict)
    output_data = Column(JSONB, default=dict)
    state_snapshots = Column(JSONB, default=list)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    agent = relationship("Agent", back_populates="runs")
