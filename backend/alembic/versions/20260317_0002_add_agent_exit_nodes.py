"""add agent exit_nodes support

Revision ID: 20260317_0002
Revises: 20260317_0001
Create Date: 2026-03-17 00:05:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260317_0002"
down_revision = "20260317_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "exit_nodes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE agents
            SET exit_nodes = CASE
                WHEN exit_node IS NULL OR btrim(exit_node) = '' THEN '[]'::jsonb
                ELSE jsonb_build_array(exit_node)
            END
            """
        )
    )


def downgrade() -> None:
    op.drop_column("agents", "exit_nodes")
