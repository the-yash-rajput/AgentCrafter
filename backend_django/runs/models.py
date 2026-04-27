"""
Django ORM model for Run.

A Run records one execution of an agent graph, including its input/output,
state snapshots captured at each node, and any error message.

Mirrors the SQLAlchemy Run model (models/run.py).
"""
from django.db import models


class RunStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    INTERRUPTED = "interrupted", "Interrupted"  # mid-execution crash; can resume


class Run(models.Model):
    """
    Execution record for a single agent graph run.

    state_snapshots stores a list of per-node state dicts captured during
    execution and streamed back to the frontend via the /stream SSE endpoint.
    """
    # FK to agents.Agent — uses string reference to avoid circular imports
    agent = models.ForeignKey(
        "agents.Agent",
        on_delete=models.CASCADE,
        related_name="runs",
        db_column="agent_id",
    )
    version = models.ForeignKey(
        "agents.AgentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runs",
        db_column="version_id",
    )
    session = models.ForeignKey(
        "agent_sessions.AgentSession",  # label set in sessions/apps.py to avoid clash with django.contrib.sessions
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runs",
        db_column="session_id",
    )
    status = models.CharField(
        max_length=20,
        choices=RunStatus.choices,
        default=RunStatus.PENDING,
    )
    # state_snapshots is the list of per-node states used by the /stream endpoint
    state_snapshots = models.JSONField(default=list)
    message = models.TextField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    checkpoint_thread_id = models.UUIDField(null=True, blank=True, db_index=True)
    resumed_from_run = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resume_runs",
        db_column="resumed_from_run_id",
    )
    pause_requested = models.BooleanField(default=False)
    interrupt_metadata = models.JSONField(null=True, blank=True, default=None)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "runs"
        indexes = [
            models.Index(fields=["agent", "started_at"], name="ix_runs_agent_started_at"),
            models.Index(fields=["status"], name="ix_runs_status"),
        ]

    def __str__(self):
        return f"Run {self.id} ({self.status})"
