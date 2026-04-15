"""
SQLAlchemy session helper for Django views.

The service layer (services/, runtime/) was written for FastAPI and uses
SQLAlchemy sessions directly. This module provides a context-manager wrapper
so Django views can open/commit/close a session without the FastAPI
Depends(get_db) dependency injection mechanism.

Usage in a view:
    from config.db import managed_db
    with managed_db() as db:
        agent = AgentService(db).get_agent(agent_id)
"""
from contextlib import contextmanager

from db.session import SessionLocal  # Reused from the copied db/ package


@contextmanager
def managed_db():
    """
    Yield a SQLAlchemy session and guarantee clean-up.

    Commits on success, rolls back on any exception, always closes.
    Equivalent to the FastAPI get_db() generator used via Depends().
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
