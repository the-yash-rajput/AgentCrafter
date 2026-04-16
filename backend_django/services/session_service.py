from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from models.agent_session import AgentSession
from services.exceptions import NotFoundError
from services.session_history import normalize_conversation_history


class SessionService:
    def __init__(self, db: Session):
        self.db = db

    def create_session(self, agent_id: int, version_id: int) -> AgentSession:
        session = AgentSession(
            agent_id=agent_id,
            version_id=version_id,
            conversation_history=[],
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: int) -> AgentSession:
        session = self.db.query(AgentSession).filter(AgentSession.id == session_id).first()
        if not session:
            raise NotFoundError("Session not found")
        return session

    def list_sessions(self, agent_id: int, version_id: int) -> list[AgentSession]:
        return (
            self.db.query(AgentSession)
            .filter(AgentSession.agent_id == agent_id, AgentSession.version_id == version_id)
            .order_by(AgentSession.created_at.desc())
            .all()
        )

    def append_conversation_turn(self, session_id: int, turn: list[dict]) -> None:
        if not turn:
            return
        session = self.get_session(session_id)
        current = normalize_conversation_history(session.conversation_history)
        current.extend(normalize_conversation_history(turn))
        session.conversation_history = current
        session.updated_at = datetime.utcnow()
        self.db.commit()
