"""
DRF serializers for the runs app.

RunResponseSerializer converts the SQLAlchemy Run model instance returned
by RunService into the same JSON shape as the FastAPI RunResponse Pydantic
schema.
"""
from rest_framework import serializers


class RunResponseSerializer(serializers.Serializer):
    """
    Read serializer for Run objects.

    Receives SQLAlchemy Run model instances (not Django ORM instances).
    The status field is an enum on the SQLAlchemy model — we call .value to
    get the string, mirroring the FastAPI behaviour.
    """
    id = serializers.IntegerField()
    agent_id = serializers.IntegerField()
    version_id = serializers.IntegerField(allow_null=True)
    session_id = serializers.IntegerField(allow_null=True)
    # status is a RunStatus enum on the SQLAlchemy model; .value gives "success" etc.
    status = serializers.SerializerMethodField()
    message = serializers.CharField(allow_null=True)
    state_snapshots = serializers.JSONField()
    error = serializers.CharField(allow_null=True)
    checkpoint_thread_id = serializers.UUIDField(allow_null=True)
    resumed_from_run_id = serializers.IntegerField(allow_null=True)
    interrupt_metadata = serializers.JSONField(allow_null=True)
    sla_timeout_at = serializers.DateTimeField(allow_null=True)
    review_metadata = serializers.JSONField(allow_null=True)
    started_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)

    def get_status(self, obj):
        # SQLAlchemy enum — extract string value
        s = obj.status
        return s.value if hasattr(s, "value") else s
