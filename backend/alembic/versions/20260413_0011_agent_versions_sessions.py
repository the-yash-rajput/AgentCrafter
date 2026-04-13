"""add agent versions and sessions

Revision ID: 20260413_0011
Revises: 20260408_0010
Create Date: 2026-04-13 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260413_0011"
down_revision = "20260408_0010"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _columns(inspector: sa.Inspector, table_name: str) -> set[str]:
    if not _table_exists(inspector, table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _indexes(inspector: sa.Inspector, table_name: str) -> set[str]:
    if not _table_exists(inspector, table_name):
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _constraints(inspector: sa.Inspector, table_name: str) -> set[str]:
    if not _table_exists(inspector, table_name):
        return set()
    names = {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}
    names.update(constraint["name"] for constraint in inspector.get_foreign_keys(table_name))
    return {name for name in names if name}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "agent_versions"):
        op.create_table(
            "agent_versions",
            sa.Column("id", sa.BigInteger(), sa.Identity(start=1), nullable=False),
            sa.Column("agent_id", sa.BigInteger(), nullable=False),
            sa.Column("version_number", sa.BigInteger(), nullable=False),
            sa.Column("base_version_id", sa.BigInteger(), nullable=True),
            sa.Column(
                "state_schema",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("entry_node", sa.String(length=255), nullable=True),
            sa.Column(
                "exit_nodes",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["base_version_id"], ["agent_versions.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("agent_id", "version_number", name="uq_agent_versions_agent_number"),
        )
        op.create_index("ix_agent_versions_agent_id", "agent_versions", ["agent_id"], unique=False)
        op.create_index(
            "ix_agent_versions_agent_created_at",
            "agent_versions",
            ["agent_id", "created_at"],
            unique=False,
        )

    op.execute(
        sa.text(
            """
            INSERT INTO agent_versions (
                agent_id, version_number, state_schema, entry_node, exit_nodes, metadata, created_at, updated_at
            )
            SELECT
                agents.id,
                1,
                COALESCE(agents.state_schema, '{}'::jsonb),
                agents.entry_node,
                COALESCE(agents.exit_nodes, '[]'::jsonb),
                COALESCE(agents.metadata, '{}'::jsonb),
                agents.created_at,
                agents.updated_at
            FROM agents
            WHERE NOT EXISTS (
                SELECT 1 FROM agent_versions WHERE agent_versions.agent_id = agents.id
            )
            """
        )
    )

    inspector = sa.inspect(bind)
    node_columns = _columns(inspector, "nodes")
    if "agent_version_id" not in node_columns:
        op.add_column("nodes", sa.Column("agent_version_id", sa.BigInteger(), nullable=True))
        op.create_index("ix_nodes_agent_version_id", "nodes", ["agent_version_id"], unique=False)
    op.execute(
        sa.text(
            """
            UPDATE nodes
            SET agent_version_id = agent_versions.id
            FROM agent_versions
            WHERE nodes.agent_id = agent_versions.agent_id
              AND agent_versions.version_number = 1
              AND nodes.agent_version_id IS NULL
            """
        )
    )

    inspector = sa.inspect(bind)
    constraints = _constraints(inspector, "nodes")
    if "uq_nodes_agent_name" in constraints:
        op.drop_constraint("uq_nodes_agent_name", "nodes", type_="unique")
    if "uq_nodes_agent_version_name" not in constraints:
        op.create_unique_constraint("uq_nodes_agent_version_name", "nodes", ["agent_version_id", "name"])
    if "uq_nodes_agent_version_id_id" not in constraints:
        op.create_unique_constraint("uq_nodes_agent_version_id_id", "nodes", ["agent_version_id", "id"])
    if "fk_nodes_agent_version_id_agent_versions" not in constraints:
        op.create_foreign_key(
            "fk_nodes_agent_version_id_agent_versions",
            "nodes",
            "agent_versions",
            ["agent_version_id"],
            ["id"],
            ondelete="CASCADE",
        )
    indexes = _indexes(sa.inspect(bind), "nodes")
    if "ix_nodes_agent_version_created_at" not in indexes:
        op.create_index(
            "ix_nodes_agent_version_created_at",
            "nodes",
            ["agent_version_id", "created_at"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    edge_columns = _columns(inspector, "edges")
    if "agent_version_id" not in edge_columns:
        op.add_column("edges", sa.Column("agent_version_id", sa.BigInteger(), nullable=True))
        op.create_index("ix_edges_agent_version_id", "edges", ["agent_version_id"], unique=False)
    op.execute(
        sa.text(
            """
            UPDATE edges
            SET agent_version_id = agent_versions.id
            FROM agent_versions
            WHERE edges.agent_id = agent_versions.agent_id
              AND agent_versions.version_number = 1
              AND edges.agent_version_id IS NULL
            """
        )
    )

    inspector = sa.inspect(bind)
    constraints = _constraints(inspector, "edges")
    if "fk_edges_agent_version_id_agent_versions" not in constraints:
        op.create_foreign_key(
            "fk_edges_agent_version_id_agent_versions",
            "edges",
            "agent_versions",
            ["agent_version_id"],
            ["id"],
            ondelete="CASCADE",
        )
    if "fk_edges_version_source_node" not in constraints:
        op.create_foreign_key(
            "fk_edges_version_source_node",
            "edges",
            "nodes",
            ["agent_version_id", "source_node_id"],
            ["agent_version_id", "id"],
            ondelete="CASCADE",
            onupdate="CASCADE",
        )
    if "fk_edges_version_target_node" not in constraints:
        op.create_foreign_key(
            "fk_edges_version_target_node",
            "edges",
            "nodes",
            ["agent_version_id", "target_node_id"],
            ["agent_version_id", "id"],
            ondelete="CASCADE",
            onupdate="CASCADE",
        )
    indexes = _indexes(sa.inspect(bind), "edges")
    if "ix_edges_agent_version_source" not in indexes:
        op.create_index("ix_edges_agent_version_source", "edges", ["agent_version_id", "source_node_id"])
    if "ix_edges_agent_version_target" not in indexes:
        op.create_index("ix_edges_agent_version_target", "edges", ["agent_version_id", "target_node_id"])
    if "ix_edges_agent_version_created_at" not in indexes:
        op.create_index("ix_edges_agent_version_created_at", "edges", ["agent_version_id", "created_at"])

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "agent_sessions"):
        op.create_table(
            "agent_sessions",
            sa.Column("id", sa.BigInteger(), sa.Identity(start=1), nullable=False),
            sa.Column("agent_id", sa.BigInteger(), nullable=False),
            sa.Column("agent_version_id", sa.BigInteger(), nullable=False),
            sa.Column(
                "conversation_history",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["agent_version_id"], ["agent_versions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_agent_sessions_agent_id", "agent_sessions", ["agent_id"], unique=False)
        op.create_index("ix_agent_sessions_agent_version_id", "agent_sessions", ["agent_version_id"], unique=False)
        op.create_index(
            "ix_agent_sessions_agent_version_updated_at",
            "agent_sessions",
            ["agent_id", "agent_version_id", "updated_at"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    run_columns = _columns(inspector, "runs")
    if "agent_version_id" not in run_columns:
        op.add_column("runs", sa.Column("agent_version_id", sa.BigInteger(), nullable=True))
        op.create_index("ix_runs_agent_version_id", "runs", ["agent_version_id"], unique=False)
    if "parent_run_id" not in run_columns:
        op.add_column("runs", sa.Column("parent_run_id", sa.BigInteger(), nullable=True))
        op.create_index("ix_runs_parent_run_id", "runs", ["parent_run_id"], unique=False)

    op.execute(
        sa.text(
            """
            UPDATE runs
            SET agent_version_id = agent_versions.id
            FROM agent_versions
            WHERE runs.agent_id = agent_versions.agent_id
              AND agent_versions.version_number = 1
              AND runs.agent_version_id IS NULL
            """
        )
    )

    inspector = sa.inspect(bind)
    run_columns = {column["name"]: column for column in inspector.get_columns("runs")}
    if "session_id" in run_columns and not isinstance(run_columns["session_id"]["type"], sa.BigInteger):
        run_indexes = _indexes(inspector, "runs")
        if "ix_runs_agent_session_started_at" in run_indexes:
            op.drop_index("ix_runs_agent_session_started_at", table_name="runs")
        op.alter_column(
            "runs",
            "session_id",
            existing_nullable=True,
            type_=sa.BigInteger(),
            postgresql_using=(
                "CASE WHEN session_id ~ '^[0-9]+$' "
                "THEN session_id::bigint ELSE NULL END"
            ),
        )
    op.execute(sa.text("UPDATE runs SET session_id = NULL WHERE session_id IS NOT NULL"))

    inspector = sa.inspect(bind)
    constraints = _constraints(inspector, "runs")
    if "fk_runs_agent_version_id_agent_versions" not in constraints:
        op.create_foreign_key(
            "fk_runs_agent_version_id_agent_versions",
            "runs",
            "agent_versions",
            ["agent_version_id"],
            ["id"],
            ondelete="CASCADE",
        )
    if "fk_runs_session_id_agent_sessions" not in constraints:
        op.create_foreign_key(
            "fk_runs_session_id_agent_sessions",
            "runs",
            "agent_sessions",
            ["session_id"],
            ["id"],
            ondelete="CASCADE",
        )
    if "fk_runs_parent_run_id_runs" not in constraints:
        op.create_foreign_key(
            "fk_runs_parent_run_id_runs",
            "runs",
            "runs",
            ["parent_run_id"],
            ["id"],
            ondelete="SET NULL",
        )

    run_indexes = _indexes(sa.inspect(bind), "runs")
    if "ix_runs_agent_version_started_at" not in run_indexes:
        op.create_index(
            "ix_runs_agent_version_started_at",
            "runs",
            ["agent_id", "agent_version_id", "started_at"],
        )
    if "ix_runs_agent_session_started_at" not in run_indexes:
        op.create_index(
            "ix_runs_agent_session_started_at",
            "runs",
            ["agent_id", "session_id", "started_at"],
        )

    inspector = sa.inspect(bind)
    run_columns = _columns(inspector, "runs")
    if "conversation_turn" in run_columns:
        op.drop_column("runs", "conversation_turn")
    if "conversation_history" in run_columns:
        op.drop_column("runs", "conversation_history")


def downgrade() -> None:
    pass
