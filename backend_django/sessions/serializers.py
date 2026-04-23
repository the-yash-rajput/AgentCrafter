"""
DRF serializers for the sessions app.
"""
from rest_framework import serializers


class SessionResponseSerializer(serializers.Serializer):
    """Read serializer for AgentSession SQLAlchemy model instances."""
    id = serializers.IntegerField()
    agent_id = serializers.IntegerField()
    version_id = serializers.IntegerField()
    conversation_history = serializers.JSONField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class SessionRunCreateSerializer(serializers.Serializer):
    """Validates the request body for POST .../sessions/{id}/run."""
    message = serializers.CharField(required=True, allow_blank=False)
    metadata = serializers.DictField(required=False, default=dict)
