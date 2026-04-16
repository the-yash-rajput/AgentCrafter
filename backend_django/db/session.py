import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.base import Base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://langgraph:langgraph_secret@localhost:5733/ldb")
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "40"))
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT,
    pool_recycle=DB_POOL_RECYCLE,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    from models import Agent, Node, Edge, Run  # noqa
    from models.agent_version import AgentVersion  # noqa
    from models.agent_session import AgentSession  # noqa
    Base.metadata.create_all(bind=engine)
