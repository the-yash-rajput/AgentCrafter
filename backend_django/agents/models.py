"""
Django ORM models for Agent, AgentVersion, Node, and Edge.

These models exist for two purposes:
  1. Django migrations — generate and apply DDL changes to PostgreSQL.
  2. Django Admin — browse and manage records via /admin/.

All runtime data access (service layer) still goes through the SQLAlchemy
models in models/ (copied verbatim from the FastAPI backend). Django ORM
and SQLAlchemy point at the same PostgreSQL tables; they coexist safely.

Key mapping decisions:
  - SQLAlchemy BigInteger Identity → Django BigAutoField (set as DEFAULT_AUTO_FIELD)
  - SQLAlchemy SAEnum(PgType) → CharField with TextChoices (avoids PG enum DDL conflicts)
  - SQLAlchemy JSONB → models.JSONField (requires django.contrib.postgres)
  - Composite FK on edges (agent_id + source/target_node_id) → added via RunSQL migration
"""
from django.db import models


# ── Enum choices ──────────────────────────────────────────────────────────────

class AgentStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class NodeType(models.TextChoices):
    FUNCTIONAL = "functional", "Functional"
    LLM_CALL = "llm_call", "LLM Call"
    COMMUNICATION = "communication", "Communication"


class NodeSubtype(models.TextChoices):
    PYTHON_INLINE = "python_inline", "Python Inline"
    API_CALL = "api_call", "API Call"
    AGENT_CALL = "agent_call", "Agent Call"
    CHAT = "chat", "Chat"
    LLM_AGENT = "llm_agent", "LLM Agent"
    RABBITMQ_MESSAGE = "rabbitmq_message", "RabbitMQ Message"
    KAFKA = "kafka", "Kafka"
    API = "api", "API"


class EdgeType(models.TextChoices):
    DIRECT = "direct", "Direct"
    CONDITIONAL = "conditional", "Conditional"


# ── Agent ─────────────────────────────────────────────────────────────────────

class Agent(models.Model):
    """
    Top-level workflow entity. Holds metadata and links to nodes/edges via
    AgentVersion snapshots.

    Mirrors the SQLAlchemy Agent model (models/agent.py).
    """
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=AgentStatus.choices,
        default=AgentStatus.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agents"
        indexes = [
            models.Index(fields=["status", "created_at"], name="ix_agents_status_created_at"),
            models.Index(fields=["created_at"], name="ix_agents_created_at"),
        ]

    def __str__(self):
        return f"{self.name} ({self.status})"


# ── AgentVersion ──────────────────────────────────────────────────────────────

class AgentVersion(models.Model):
    """
    Immutable snapshot of an agent's configuration at a point in time.

    Mirrors the SQLAlchemy AgentVersion model (models/agent_version.py).
    """
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="versions",
        db_column="agent_id",
    )
    version_number = models.IntegerField()
    entry_node = models.CharField(max_length=255, null=True, blank=True)
    exit_nodes = models.JSONField(default=list)
    state_schema = models.JSONField(default=dict)
    # Self-referential FK tracking which version this was forked from.
    created_from_version = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="forked_versions",
        db_column="created_from_version_id",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_versions"
        constraints = [
            models.UniqueConstraint(
                fields=["agent", "version_number"],
                name="uq_agent_versions_agent_version",
            )
        ]

    def __str__(self):
        return f"v{self.version_number} of {self.agent_id}"


# ── Node ──────────────────────────────────────────────────────────────────────

class Node(models.Model):
    """
    A single processing step within an agent graph.

    Mirrors the SQLAlchemy Node model (models/node.py).
    The composite unique constraint (agent_id, id) is required so that the
    edges table can reference nodes via a composite foreign key. This is added
    via RunSQL in the migration because Django cannot express multi-column FKs.
    """
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="nodes",
        db_column="agent_id",
    )
    version = models.ForeignKey(
        AgentVersion,
        on_delete=models.CASCADE,
        related_name="nodes",
        db_column="version_id",
    )
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=30, choices=NodeType.choices)
    subtype = models.CharField(
        max_length=30,
        choices=NodeSubtype.choices,
        default=NodeSubtype.PYTHON_INLINE,
    )
    config = models.JSONField(default=dict)
    position_x = models.FloatField(default=0.0)
    position_y = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "nodes"
        constraints = [
            # Required for conditional routing — name must be unique per version.
            models.UniqueConstraint(
                fields=["version", "name"],
                name="uq_nodes_version_name",
            ),
            # Required so edges can use a composite FK (agent_id, node_id).
            models.UniqueConstraint(
                fields=["agent", "id"],
                name="uq_nodes_agent_id_id",
            ),
        ]
        indexes = [
            models.Index(fields=["agent", "created_at"], name="ix_nodes_agent_created_at"),
        ]

    def __str__(self):
        return f"{self.name} ({self.type}/{self.subtype})"


# ── Edge ──────────────────────────────────────────────────────────────────────

class Edge(models.Model):
    """
    A directed connection between two nodes in an agent graph.

    source_node_id / target_node_id are plain BigIntegerFields because Django
    cannot express the composite (agent_id, node_id) foreign key. The actual
    DB-level constraints (fk_edges_source_node, fk_edges_target_node) are
    added via RunSQL in the initial migration, matching what Alembic created.

    Mirrors the SQLAlchemy Edge model (models/edge.py).
    """
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="edges",
        db_column="agent_id",
    )
    version = models.ForeignKey(
        AgentVersion,
        on_delete=models.CASCADE,
        related_name="edges",
        db_column="version_id",
    )
    # Raw IDs — cannot use ForeignKey because the constraint is composite.
    source_node_id = models.BigIntegerField()
    target_node_id = models.BigIntegerField()
    edge_type = models.CharField(
        max_length=20,
        choices=EdgeType.choices,
        default=EdgeType.DIRECT,
    )
    condition_config = models.JSONField(default=dict)
    label = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "edges"
        indexes = [
            models.Index(fields=["agent", "source_node_id"], name="ix_edges_agent_source"),
            models.Index(fields=["agent", "target_node_id"], name="ix_edges_agent_target"),
            models.Index(fields=["agent", "created_at"], name="ix_edges_agent_created_at"),
        ]

    def __str__(self):
        return f"Edge {self.source_node_id}→{self.target_node_id} ({self.edge_type})"
