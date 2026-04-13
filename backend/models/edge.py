from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.base import Base
from models.enums import EdgeType


class Edge(Base):
    __tablename__ = "edges"

    id = Column(BigInteger, Identity(start=1), primary_key=True)
    agent_id = Column(BigInteger, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_version_id = Column(
        BigInteger,
        ForeignKey("agent_versions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source_node_id = Column(BigInteger, nullable=False)
    target_node_id = Column(BigInteger, nullable=False)
    edge_type = Column(SAEnum(EdgeType, name="edge_type"), default=EdgeType.direct, nullable=False)
    condition_config = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    label = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    agent = relationship("Agent", back_populates="edges")
    agent_version = relationship("AgentVersion", back_populates="edges")

    __table_args__ = (
        ForeignKeyConstraint(
            ["agent_id", "source_node_id"],
            ["nodes.agent_id", "nodes.id"],
            name="fk_edges_source_node",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        ForeignKeyConstraint(
            ["agent_version_id", "source_node_id"],
            ["nodes.agent_version_id", "nodes.id"],
            name="fk_edges_version_source_node",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        ForeignKeyConstraint(
            ["agent_version_id", "target_node_id"],
            ["nodes.agent_version_id", "nodes.id"],
            name="fk_edges_version_target_node",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        Index("ix_edges_agent_version_source", "agent_version_id", "source_node_id"),
        Index("ix_edges_agent_version_target", "agent_version_id", "target_node_id"),
        Index("ix_edges_agent_version_created_at", "agent_version_id", "created_at"),
        ForeignKeyConstraint(
            ["agent_id", "target_node_id"],
            ["nodes.agent_id", "nodes.id"],
            name="fk_edges_target_node",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        Index("ix_edges_agent_source", "agent_id", "source_node_id"),
        Index("ix_edges_agent_target", "agent_id", "target_node_id"),
        Index("ix_edges_agent_created_at", "agent_id", "created_at"),
    )
