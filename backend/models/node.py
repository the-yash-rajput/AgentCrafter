from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Identity,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.base import Base
from models.enums import NodeSubtype, NodeType


class Node(Base):
    __tablename__ = "nodes"

    id = Column(BigInteger, Identity(start=1), primary_key=True)
    agent_id = Column(BigInteger, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_version_id = Column(
        BigInteger,
        ForeignKey("agent_versions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name = Column(String(255), nullable=False)
    type = Column(SAEnum(NodeType, name="node_type"), nullable=False)
    subtype = Column(
        SAEnum(NodeSubtype, name="node_subtype"),
        nullable=False,
        default=NodeSubtype.python_inline,
        server_default=NodeSubtype.python_inline.value,
    )
    config = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    position_x = Column(Float, default=0.0)
    position_y = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    agent = relationship("Agent", back_populates="nodes")
    agent_version = relationship("AgentVersion", back_populates="nodes")

    __table_args__ = (
        UniqueConstraint("agent_version_id", "name", name="uq_nodes_agent_version_name"),
        # Required for composite foreign keys from edges(agent_id, *_node_id).
        UniqueConstraint("agent_id", "id", name="uq_nodes_agent_id_id"),
        UniqueConstraint("agent_version_id", "id", name="uq_nodes_agent_version_id_id"),
        Index("ix_nodes_agent_created_at", "agent_id", "created_at"),
        Index("ix_nodes_agent_version_created_at", "agent_version_id", "created_at"),
    )
