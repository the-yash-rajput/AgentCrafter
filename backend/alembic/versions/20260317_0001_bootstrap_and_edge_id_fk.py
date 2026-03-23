"""bootstrap schema and migrate edges to node-id FKs

Revision ID: 20260317_0001
Revises:
Create Date: 2026-03-17 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260317_0001"
down_revision = None
branch_labels = None
depends_on = None


def _constraint_exists(bind, name: str) -> bool:
    query = sa.text(
        """
        SELECT 1
        FROM information_schema.table_constraints
        WHERE constraint_name = :name
        LIMIT 1
        """
    )
    return bind.execute(query, {"name": name}).scalar() is not None


def _index_exists(bind, name: str) -> bool:
    query = sa.text(
        """
        SELECT 1
        FROM pg_indexes
        WHERE indexname = :name
        LIMIT 1
        """
    )
    return bind.execute(query, {"name": name}).scalar() is not None


def _create_full_schema() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.BigInteger(), sa.Identity(start=1), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("draft", "active", "archived", name="agent_status"), nullable=False),
        sa.Column("input_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("state_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("entry_node", sa.String(length=255), nullable=True),
        sa.Column("exit_node", sa.String(length=255), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agents_status_created_at", "agents", ["status", "created_at"])
    op.create_index("ix_agents_created_at", "agents", ["created_at"])

    op.create_table(
        "nodes",
        sa.Column("id", sa.BigInteger(), sa.Identity(start=1), primary_key=True),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.Enum("functional", "llm_call", name="node_type"), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("position_x", sa.Float(), nullable=True),
        sa.Column("position_y", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("agent_id", "name", name="uq_nodes_agent_name"),
        sa.UniqueConstraint("agent_id", "id", name="uq_nodes_agent_id_id"),
    )
    op.create_index("ix_nodes_agent_id", "nodes", ["agent_id"])
    op.create_index("ix_nodes_agent_created_at", "nodes", ["agent_id", "created_at"])

    op.create_table(
        "edges",
        sa.Column("id", sa.BigInteger(), sa.Identity(start=1), primary_key=True),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.Column("source_node_id", sa.BigInteger(), nullable=False),
        sa.Column("target_node_id", sa.BigInteger(), nullable=False),
        sa.Column("edge_type", sa.Enum("direct", "conditional", name="edge_type"), nullable=False),
        sa.Column("condition_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id", "source_node_id"], ["nodes.agent_id", "nodes.id"], name="fk_edges_source_node", ondelete="CASCADE", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id", "target_node_id"], ["nodes.agent_id", "nodes.id"], name="fk_edges_target_node", ondelete="CASCADE", onupdate="CASCADE"),
    )
    op.create_index("ix_edges_agent_id", "edges", ["agent_id"])
    op.create_index("ix_edges_agent_source", "edges", ["agent_id", "source_node_id"])
    op.create_index("ix_edges_agent_target", "edges", ["agent_id", "target_node_id"])
    op.create_index("ix_edges_agent_created_at", "edges", ["agent_id", "created_at"])

    op.create_table(
        "runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(start=1), primary_key=True),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Enum("pending", "running", "success", "failed", name="run_status"), nullable=False),
        sa.Column("input_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("state_snapshots", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_runs_agent_id", "runs", ["agent_id"])
    op.create_index("ix_runs_status", "runs", ["status"])
    op.create_index("ix_runs_agent_started_at", "runs", ["agent_id", "started_at"])


def _migrate_existing_edges_to_id_fk(bind) -> None:
    inspector = sa.inspect(bind)
    columns = {c["name"]: c for c in inspector.get_columns("edges")}
    source_col = columns.get("source_node_id")
    target_col = columns.get("target_node_id")
    if source_col is None or target_col is None:
        return

    source_is_bigint = isinstance(source_col["type"], sa.BigInteger)
    target_is_bigint = isinstance(target_col["type"], sa.BigInteger)
    if source_is_bigint and target_is_bigint:
        return

    if not _constraint_exists(bind, "uq_nodes_agent_id_id"):
        op.create_unique_constraint("uq_nodes_agent_id_id", "nodes", ["agent_id", "id"])

    if "source_node_ref_id" not in columns:
        op.add_column("edges", sa.Column("source_node_ref_id", sa.BigInteger(), nullable=True))
    if "target_node_ref_id" not in columns:
        op.add_column("edges", sa.Column("target_node_ref_id", sa.BigInteger(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE edges e
            SET source_node_ref_id = n.id
            FROM nodes n
            WHERE e.agent_id = n.agent_id
              AND CAST(e.source_node_id AS TEXT) = n.name
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE edges e
            SET target_node_ref_id = n.id
            FROM nodes n
            WHERE e.agent_id = n.agent_id
              AND CAST(e.target_node_id AS TEXT) = n.name
            """
        )
    )

    unresolved = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM edges
            WHERE source_node_ref_id IS NULL OR target_node_ref_id IS NULL
            """
        )
    ).scalar_one()
    if unresolved:
        raise RuntimeError(
            f"Edge migration aborted: {unresolved} edge rows could not be mapped from node names to IDs."
        )

    for fk_name in ("fk_edges_source_node", "fk_edges_target_node"):
        if _constraint_exists(bind, fk_name):
            op.drop_constraint(fk_name, "edges", type_="foreignkey")

    for idx_name in ("ix_edges_agent_source", "ix_edges_agent_target"):
        if _index_exists(bind, idx_name):
            op.drop_index(idx_name, table_name="edges")

    op.drop_column("edges", "source_node_id")
    op.drop_column("edges", "target_node_id")
    op.alter_column("edges", "source_node_ref_id", new_column_name="source_node_id")
    op.alter_column("edges", "target_node_ref_id", new_column_name="target_node_id")
    op.alter_column("edges", "source_node_id", existing_type=sa.BigInteger(), nullable=False)
    op.alter_column("edges", "target_node_id", existing_type=sa.BigInteger(), nullable=False)


def _ensure_constraints_and_indexes(bind) -> None:
    if not _constraint_exists(bind, "uq_nodes_agent_id_id"):
        op.create_unique_constraint("uq_nodes_agent_id_id", "nodes", ["agent_id", "id"])

    if not _constraint_exists(bind, "fk_edges_source_node"):
        op.create_foreign_key(
            "fk_edges_source_node",
            "edges",
            "nodes",
            ["agent_id", "source_node_id"],
            ["agent_id", "id"],
            ondelete="CASCADE",
            onupdate="CASCADE",
        )
    if not _constraint_exists(bind, "fk_edges_target_node"):
        op.create_foreign_key(
            "fk_edges_target_node",
            "edges",
            "nodes",
            ["agent_id", "target_node_id"],
            ["agent_id", "id"],
            ondelete="CASCADE",
            onupdate="CASCADE",
        )

    if not _index_exists(bind, "ix_agents_created_at"):
        op.create_index("ix_agents_created_at", "agents", ["created_at"])
    if not _index_exists(bind, "ix_edges_agent_created_at"):
        op.create_index("ix_edges_agent_created_at", "edges", ["agent_id", "created_at"])
    if not _index_exists(bind, "ix_edges_agent_source"):
        op.create_index("ix_edges_agent_source", "edges", ["agent_id", "source_node_id"])
    if not _index_exists(bind, "ix_edges_agent_target"):
        op.create_index("ix_edges_agent_target", "edges", ["agent_id", "target_node_id"])


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    # On a brand-new database Alembic may create `alembic_version` before
    # invoking this revision, so ignore it when deciding whether to bootstrap
    # the full application schema.
    if not (existing_tables - {"alembic_version"}):
        _create_full_schema()
        return

    if "edges" in existing_tables and "nodes" in existing_tables:
        _migrate_existing_edges_to_id_fk(bind)
    _ensure_constraints_and_indexes(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if not {"edges", "nodes"}.issubset(existing_tables):
        return

    columns = {c["name"]: c for c in inspector.get_columns("edges")}
    source_col = columns.get("source_node_id")
    target_col = columns.get("target_node_id")
    if source_col is None or target_col is None:
        return
    if isinstance(source_col["type"], sa.String) and isinstance(target_col["type"], sa.String):
        return

    if _constraint_exists(bind, "fk_edges_source_node"):
        op.drop_constraint("fk_edges_source_node", "edges", type_="foreignkey")
    if _constraint_exists(bind, "fk_edges_target_node"):
        op.drop_constraint("fk_edges_target_node", "edges", type_="foreignkey")

    op.add_column("edges", sa.Column("source_node_name", sa.String(length=255), nullable=True))
    op.add_column("edges", sa.Column("target_node_name", sa.String(length=255), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE edges e
            SET source_node_name = n.name
            FROM nodes n
            WHERE e.agent_id = n.agent_id
              AND e.source_node_id = n.id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE edges e
            SET target_node_name = n.name
            FROM nodes n
            WHERE e.agent_id = n.agent_id
              AND e.target_node_id = n.id
            """
        )
    )

    op.drop_column("edges", "source_node_id")
    op.drop_column("edges", "target_node_id")
    op.alter_column("edges", "source_node_name", new_column_name="source_node_id")
    op.alter_column("edges", "target_node_name", new_column_name="target_node_id")
    op.alter_column("edges", "source_node_id", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("edges", "target_node_id", existing_type=sa.String(length=255), nullable=False)

    op.create_foreign_key(
        "fk_edges_source_node",
        "edges",
        "nodes",
        ["agent_id", "source_node_id"],
        ["agent_id", "name"],
        ondelete="CASCADE",
        onupdate="CASCADE",
    )
    op.create_foreign_key(
        "fk_edges_target_node",
        "edges",
        "nodes",
        ["agent_id", "target_node_id"],
        ["agent_id", "name"],
        ondelete="CASCADE",
        onupdate="CASCADE",
    )
