"""drop legacy agent exit_node column

Revision ID: 20260406_0007
Revises: 20260406_0006
Create Date: 2026-04-06 16:10:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260406_0007"
down_revision = "20260406_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("agents")}
    if "exit_node" in columns:
        op.drop_column("agents", "exit_node")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("agents")}
    if "exit_node" not in columns:
        op.add_column("agents", sa.Column("exit_node", sa.String(length=255), nullable=True))
        op.execute(
            sa.text(
                """
                UPDATE agents
                SET exit_node = CASE
                    WHEN jsonb_array_length(COALESCE(exit_nodes, '[]'::jsonb)) = 0 THEN NULL
                    ELSE exit_nodes->>0
                END
                """
            )
        )
