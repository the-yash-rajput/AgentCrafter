"""drop legacy agent input and output schema columns

Revision ID: 20260407_0009
Revises: 20260407_0008
Create Date: 2026-04-07 18:10:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260407_0009"
down_revision = "20260407_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("agents")}

    if "input_schema" in columns:
        op.drop_column("agents", "input_schema")
    if "output_schema" in columns:
        op.drop_column("agents", "output_schema")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("agents")}

    if "input_schema" not in columns:
        op.add_column(
            "agents",
            sa.Column(
                "input_schema",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )
    if "output_schema" not in columns:
        op.add_column(
            "agents",
            sa.Column(
                "output_schema",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )
