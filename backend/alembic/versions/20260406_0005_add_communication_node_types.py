"""add communication node type and subtypes

Revision ID: 20260406_0005
Revises: 20260406_0004
Create Date: 2026-04-06 15:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260406_0005"
down_revision = "20260406_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    context = op.get_context()
    with context.autocommit_block():
        op.execute(sa.text("ALTER TYPE node_type ADD VALUE IF NOT EXISTS 'communication'"))
        op.execute(sa.text("ALTER TYPE node_subtype ADD VALUE IF NOT EXISTS 'rabbitmq_message'"))
        op.execute(sa.text("ALTER TYPE node_subtype ADD VALUE IF NOT EXISTS 'kafka'"))
        op.execute(sa.text("ALTER TYPE node_subtype ADD VALUE IF NOT EXISTS 'api'"))


def downgrade() -> None:
    pass
