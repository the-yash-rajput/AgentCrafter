"""
Django ORM model for AgentSession.

An AgentSession tracks multi-turn conversation state for a specific agent
version. Each session maintains a conversation_history list that grows as
turns are appended by the session service.

Mirrors the SQLAlchemy AgentSession model (models/agent_session.py).
"""
from django.db import models


class AgentSession(models.Model):
    """
    Multi-turn conversation context for an agent.

    conversation_history stores a list of turn dicts:
      [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    """
    agent = models.ForeignKey(
        "agents.Agent",
        on_delete=models.CASCADE,
        related_name="sessions",
        db_column="agent_id",
    )
    version = models.ForeignKey(
        "agents.AgentVersion",
        on_delete=models.CASCADE,
        related_name="sessions",
        db_column="version_id",
    )
    conversation_history = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agent_sessions"

    def __str__(self):
        return f"Session {self.id} (agent={self.agent_id}, v={self.version_id})"
