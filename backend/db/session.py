import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.base import Base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://langgraph:langgraph_secret@localhost:5733/langgraph_builder")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    from models.models import Agent, Node, Edge, Run  # noqa
    Base.metadata.create_all(bind=engine)
