from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Identity,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from db.base import Base
from models.enums import RunStatus


class Run(Base):
    __tablename__ = "runs"

    id = Column(BigInteger, Identity(start=1), primary_key=True)
    agent_id = Column(BigInteger, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id = Column(BigInteger, ForeignKey("agent_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(BigInteger, ForeignKey("agent_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(SAEnum(RunStatus, name="run_status"), default=RunStatus.pending, nullable=False, index=True)
    input_data = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    output_data = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    conversation_turn = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    state_snapshots = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    error = Column(Text, nullable=True)
    checkpoint_thread_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    resumed_from_run_id = Column(BigInteger, ForeignKey("runs.id", ondelete="SET NULL"), nullable=True)
    pause_requested = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    started_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    agent = relationship("Agent", back_populates="runs")
    session = relationship("AgentSession", back_populates="runs")

    __table_args__ = (
        Index("ix_runs_agent_started_at", "agent_id", "started_at"),
    )
