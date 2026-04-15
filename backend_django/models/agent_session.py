from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Identity,
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
    version_id = Column(BigInteger, ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_history = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now(), onupdate=func.now())

    agent = relationship("Agent", back_populates="sessions")
    version = relationship("AgentVersion", back_populates="sessions")
    runs = relationship("Run", back_populates="session", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = ()
