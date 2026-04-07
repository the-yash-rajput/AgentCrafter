"""add agent_audits table

Revision ID: 20260406_0001
Revises: 20260317_0002
Create Date: 2026-04-06 10:40:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260406_0001"
down_revision = "20260317_0002"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "agent_audits",
        sa.Column("id", sa.BigInteger(), sa.Identity(start=1), primary_key=True),
        sa.Column("agent_id", sa.BigInteger(), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agent_audits_agent_created_at", "agent_audits", ["agent_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_audits_agent_created_at", table_name="agent_audits")
    op.drop_table("agent_audits")
