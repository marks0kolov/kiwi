"""add users

Revision ID: 9c8a34f7b2e1
Revises: 6d1f943f53da
Create Date: 2026-07-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c8a34f7b2e1"
down_revision: Union[str, Sequence[str], None] = "6d1f943f53da"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # Preserve users from conversations created before this table existed.
    op.execute(
        """
        INSERT INTO users (user_id)
        SELECT DISTINCT user_id
        FROM conversations
        ON CONFLICT (user_id) DO NOTHING
        """
    )

    op.create_foreign_key(
        "fk_conversations_user_id_users",
        "conversations",
        "users",
        ["user_id"],
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_conversations_user_id_users",
        "conversations",
        type_="foreignkey",
    )
    op.drop_table("users")
