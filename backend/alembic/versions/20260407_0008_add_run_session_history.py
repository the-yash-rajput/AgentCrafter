"""add session history fields to runs

Revision ID: 20260407_0008
Revises: 20260406_0007
Create Date: 2026-04-07 10:40:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260407_0008"
down_revision = "20260406_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("runs")}
    indexes = {index["name"] for index in inspector.get_indexes("runs")}

    if "session_id" not in columns:
        op.add_column("runs", sa.Column("session_id", sa.Text(), nullable=True))
    if "conversation_history" not in columns:
        op.add_column(
            "runs",
            sa.Column(
                "conversation_history",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )
    if "conversation_turn" not in columns:
        op.add_column(
            "runs",
            sa.Column(
                "conversation_turn",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )

    if "ix_runs_agent_session_started_at" not in indexes:
        op.create_index(
            "ix_runs_agent_session_started_at",
            "runs",
            ["agent_id", "session_id", "started_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("runs")}
    indexes = {index["name"] for index in inspector.get_indexes("runs")}

    if "ix_runs_agent_session_started_at" in indexes:
        op.drop_index("ix_runs_agent_session_started_at", table_name="runs")
    if "conversation_turn" in columns:
        op.drop_column("runs", "conversation_turn")
    if "conversation_history" in columns:
        op.drop_column("runs", "conversation_history")
    if "session_id" in columns:
        op.drop_column("runs", "session_id")
