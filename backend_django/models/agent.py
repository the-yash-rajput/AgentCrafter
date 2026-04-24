from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum as SAEnum,
    Identity,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from db.base import Base
from models.enums import AgentStatus


class Agent(Base):
    __tablename__ = "agents"

    id = Column(BigInteger, Identity(start=1), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(AgentStatus, name="agent_status"), default=AgentStatus.draft, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now(), onupdate=func.now())

    nodes = relationship("Node", back_populates="agent", cascade="all, delete-orphan", lazy="selectin")
    edges = relationship("Edge", back_populates="agent", cascade="all, delete-orphan", lazy="selectin")
    runs = relationship("Run", back_populates="agent", cascade="all, delete-orphan", lazy="selectin")
    versions = relationship("AgentVersion", back_populates="agent", cascade="all, delete-orphan", lazy="selectin")
    sessions = relationship("AgentSession", back_populates="agent", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        Index("ix_agents_status_created_at", "status", "created_at"),
        Index("ix_agents_created_at", "created_at"),
    )
