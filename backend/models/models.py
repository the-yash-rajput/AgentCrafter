from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
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

    id = Column(BigInteger, Identity(start=1), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(AgentStatus, name="agent_status"), default=AgentStatus.draft, nullable=False)
    input_schema = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    output_schema = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    state_schema = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    entry_node = Column(String(255), nullable=True)
    exit_node = Column(String(255), nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    nodes = relationship("Node", back_populates="agent", cascade="all, delete-orphan")
    edges = relationship("Edge", back_populates="agent", cascade="all, delete-orphan")
    runs = relationship("Run", back_populates="agent", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_agents_status_created_at", "status", "created_at"),
    )


class Node(Base):
    __tablename__ = "nodes"

    id = Column(BigInteger, Identity(start=1), primary_key=True)
    agent_id = Column(BigInteger, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    type = Column(SAEnum(NodeType, name="node_type"), nullable=False)
    config = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    position_x = Column(Float, default=0.0)
    position_y = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    agent = relationship("Agent", back_populates="nodes")

    __table_args__ = (
        UniqueConstraint("agent_id", "name", name="uq_nodes_agent_name"),
        Index("ix_nodes_agent_created_at", "agent_id", "created_at"),
    )


class Edge(Base):
    __tablename__ = "edges"

    id = Column(BigInteger, Identity(start=1), primary_key=True)
    agent_id = Column(BigInteger, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    source_node_id = Column(String(255), nullable=False)
    target_node_id = Column(String(255), nullable=False)
    edge_type = Column(SAEnum(EdgeType, name="edge_type"), default=EdgeType.direct, nullable=False)
    condition_config = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    label = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    agent = relationship("Agent", back_populates="edges")

    __table_args__ = (
        ForeignKeyConstraint(
            ["agent_id", "source_node_id"],
            ["nodes.agent_id", "nodes.name"],
            name="fk_edges_source_node",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        ForeignKeyConstraint(
            ["agent_id", "target_node_id"],
            ["nodes.agent_id", "nodes.name"],
            name="fk_edges_target_node",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        Index("ix_edges_agent_source", "agent_id", "source_node_id"),
        Index("ix_edges_agent_target", "agent_id", "target_node_id"),
    )


class Run(Base):
    __tablename__ = "runs"

    id = Column(BigInteger, Identity(start=1), primary_key=True)
    agent_id = Column(BigInteger, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(SAEnum(RunStatus, name="run_status"), default=RunStatus.pending, nullable=False, index=True)
    input_data = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    output_data = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    state_snapshots = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    agent = relationship("Agent", back_populates="runs")

    __table_args__ = (
        Index("ix_runs_agent_started_at", "agent_id", "started_at"),
    )
