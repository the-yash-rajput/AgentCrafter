"""convert node subtype column to enum

Revision ID: 20260406_0004
Revises: 20260406_0003
Create Date: 2026-04-06 14:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260406_0004"
down_revision = "20260406_0003"
branch_labels = None
depends_on = None


NODE_SUBTYPE_ENUM = postgresql.ENUM(
    "python_inline",
    "api_call",
    "agent_call",
    "chat",
    name="node_subtype",
)


def upgrade() -> None:
    bind = op.get_bind()
    NODE_SUBTYPE_ENUM.create(bind, checkfirst=True)
    op.execute(
        sa.text(
            """
            ALTER TABLE nodes
            ALTER COLUMN subtype TYPE node_subtype
            USING subtype::node_subtype
            """
        )
    )
    op.alter_column("nodes", "subtype", server_default="python_inline")


def downgrade() -> None:
    op.alter_column("nodes", "subtype", type_=sa.String(length=100), server_default="python_inline")
    bind = op.get_bind()
    NODE_SUBTYPE_ENUM.drop(bind, checkfirst=True)
