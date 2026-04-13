from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.base import Base


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id = Column(BigInteger, Identity(start=1), primary_key=True)
    agent_id = Column(BigInteger, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_version_id = Column(
        BigInteger,
        ForeignKey("agent_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_history = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    last_run_at = Column(DateTime(timezone=True), nullable=True)

    agent = relationship("Agent", back_populates="sessions")
    agent_version = relationship("AgentVersion", back_populates="sessions")
    runs = relationship("Run", back_populates="session", lazy="selectin")

    __table_args__ = (
        Index("ix_agent_sessions_agent_version_updated_at", "agent_id", "agent_version_id", "updated_at"),
    )
