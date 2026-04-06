"""add explicit node subtype column

Revision ID: 20260406_0003
Revises: 20260317_0002
Create Date: 2026-04-06 12:50:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260406_0003"
down_revision = "20260317_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "nodes",
        sa.Column("subtype", sa.String(length=100), nullable=False, server_default="python_inline"),
    )
    op.execute(
        sa.text(
            """
            UPDATE nodes
            SET subtype = CASE
                WHEN type = 'functional' THEN COALESCE(NULLIF(config->>'function_type', ''), 'python_inline')
                WHEN type = 'llm_call' THEN 'chat'
                ELSE 'python_inline'
            END
            """
        )
    )
    op.alter_column("nodes", "subtype", server_default=None)


def downgrade() -> None:
    op.drop_column("nodes", "subtype")
