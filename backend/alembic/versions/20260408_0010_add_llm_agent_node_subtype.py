"""add llm agent node subtype

Revision ID: 20260408_0010
Revises: 20260407_0009
Create Date: 2026-04-08 18:10:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260408_0010"
down_revision = "20260407_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    context = op.get_context()
    with context.autocommit_block():
        op.execute(sa.text("ALTER TYPE node_subtype ADD VALUE IF NOT EXISTS 'llm_agent'"))

    op.execute(
        sa.text(
            """
            UPDATE nodes
            SET
                subtype = CASE
                    WHEN type = 'llm_call'
                        AND subtype = 'chat'
                        AND COALESCE(config->>'llm_runtime', '') = 'agent'
                    THEN 'llm_agent'::node_subtype
                    ELSE subtype
                END,
                config = CASE
                    WHEN type = 'llm_call' THEN jsonb_set(
                        COALESCE(config, '{}'::jsonb) - 'llm_runtime',
                        '{llm_type}',
                        to_jsonb(
                            CASE
                                WHEN subtype = 'chat'
                                    AND COALESCE(config->>'llm_runtime', '') = 'agent'
                                THEN 'llm_agent'
                                ELSE subtype::text
                            END
                        ),
                        true
                    )
                    ELSE COALESCE(config, '{}'::jsonb)
                END
            """
        )
    )


def downgrade() -> None:
    pass
