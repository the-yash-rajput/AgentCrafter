"""move functional api_call nodes to communication api

Revision ID: 20260406_0006
Revises: 20260406_0005
Create Date: 2026-04-06 15:20:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260406_0006"
down_revision = "20260406_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE nodes
            SET
                type = 'communication',
                subtype = 'api',
                config = jsonb_set(
                    jsonb_set(
                        COALESCE(config, '{}'::jsonb),
                        '{node_type}',
                        to_jsonb('communication'::text),
                        true
                    ),
                    '{communication_type}',
                    to_jsonb('api'::text),
                    true
                )
                || CASE
                    WHEN COALESCE(config, '{}'::jsonb) ? 'api' THEN '{}'::jsonb
                    WHEN COALESCE(config, '{}'::jsonb) ? 'api_call' THEN jsonb_build_object('api', config->'api_call')
                    ELSE '{}'::jsonb
                END
            WHERE type = 'functional'
              AND (
                subtype = 'api_call'
                OR COALESCE(config->>'function_type', '') = 'api_call'
              )
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE nodes
            SET
                type = 'functional',
                subtype = 'api_call',
                config = jsonb_set(
                    jsonb_set(
                        COALESCE(config, '{}'::jsonb),
                        '{node_type}',
                        to_jsonb('functional'::text),
                        true
                    ),
                    '{function_type}',
                    to_jsonb('api_call'::text),
                    true
                )
                || CASE
                    WHEN COALESCE(config, '{}'::jsonb) ? 'api_call' THEN '{}'::jsonb
                    WHEN COALESCE(config, '{}'::jsonb) ? 'api' THEN jsonb_build_object('api_call', config->'api')
                    ELSE '{}'::jsonb
                END
            WHERE type = 'communication'
              AND subtype = 'api'
              AND COALESCE(config->>'function_type', '') = 'api_call'
            """
        )
    )
