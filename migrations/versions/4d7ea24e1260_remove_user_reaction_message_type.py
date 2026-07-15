"""remove user reaction message type

Revision ID: 4d7ea24e1260
Revises: 9c8a34f7b2e1
Create Date: 2026-07-14

"""
from typing import Sequence, Union

from alembic import op


revision: str = "4d7ea24e1260"
down_revision: Union[str, Sequence[str], None] = "9c8a34f7b2e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MESSAGE_TYPES = (
    "SYSTEM_MESSAGE",
    "TOOL_RESPONSE",
    "USER_MESSAGE",
    "USER_ACTION",
    "KIWI_MESSAGE",
    "KIWI_REACTION",
)


def _replace_message_type(values: tuple[str, ...]) -> None:
    enum_values = ", ".join(f"'{value}'" for value in values)

    op.execute("ALTER TYPE message_type RENAME TO message_type_old")
    op.execute(f"CREATE TYPE message_type AS ENUM ({enum_values})")
    op.execute(
        """
        ALTER TABLE messages
        ALTER COLUMN message_type TYPE message_type
        USING message_type::text::message_type
        """
    )
    op.execute("DROP TYPE message_type_old")


def upgrade() -> None:
    # Private chats never receive user reaction updates. Remove any legacy rows
    # before narrowing the enum to message types Kiwi can actually persist.
    op.execute("DELETE FROM messages WHERE message_type = 'USER_REACTION'")
    _replace_message_type(MESSAGE_TYPES)


def downgrade() -> None:
    user_reaction_index = MESSAGE_TYPES.index("KIWI_MESSAGE")
    values = (
        *MESSAGE_TYPES[:user_reaction_index],
        "USER_REACTION",
        *MESSAGE_TYPES[user_reaction_index:],
    )
    _replace_message_type(values)
