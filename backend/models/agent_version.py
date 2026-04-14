from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.base import Base


class AgentVersion(Base):
    __tablename__ = "agent_versions"

    id = Column(BigInteger, Identity(start=1), primary_key=True)
    agent_id = Column(BigInteger, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    entry_node = Column(String(255), nullable=True)
    exit_nodes = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    state_schema = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_from_version_id = Column(BigInteger, ForeignKey("agent_versions.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    agent = relationship("Agent", back_populates="versions")
    nodes = relationship("Node", back_populates="version", cascade="all, delete-orphan", lazy="selectin")
    edges = relationship("Edge", back_populates="version", cascade="all, delete-orphan", lazy="selectin")
    sessions = relationship("AgentSession", back_populates="version", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("agent_id", "version_number", name="uq_agent_versions_agent_version"),
    )
