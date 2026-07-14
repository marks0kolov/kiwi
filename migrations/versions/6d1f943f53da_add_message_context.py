"""add message context

Revision ID: 6d1f943f53da
Revises: 9952e814057f
Create Date: 2026-07-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "6d1f943f53da"
down_revision: Union[str, Sequence[str], None] = "9952e814057f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "context",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE messages
        SET context = jsonb_build_object('to_id', message_id),
            message_id = NULL
        WHERE message_type IN ('USER_REACTION', 'KIWI_REACTION')
          AND message_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE messages
        SET message_id = (context ->> 'to_id')::bigint
        WHERE message_type IN ('USER_REACTION', 'KIWI_REACTION')
          AND context ? 'to_id'
        """
    )
    op.drop_column("messages", "context")
