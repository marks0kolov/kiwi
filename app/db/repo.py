from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Conversation,
    Message,
    MessageType,
)


async def create_conversation(
    session: AsyncSession,
    user_id: int,
) -> Conversation:
    "Create a new conversation"
    conversation = Conversation(user_id=user_id)

    session.add(conversation)
    await session.flush()
    await session.refresh(conversation)

    return conversation


async def get_current_conversation(
    session: AsyncSession,
    user_id: int,
) -> Conversation | None:
    "Get most recent conversation for user"
    statement = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.id.desc())
        .limit(1)
    )

    return await session.scalar(statement)


async def create_message(
    session: AsyncSession,
    *,
    conversation_id: int,
    message_type: MessageType,
    content: str,
    message_id: int | None = None,
) -> Message:
    "Create a message"
    message = Message(
        conversation_id=conversation_id,
        message_id=message_id,
        message_type=message_type,
        content=content,
    )

    session.add(message)
    await session.flush()
    await session.refresh(message)

    return message


async def get_messages(
    session: AsyncSession,
    conversation_id: int,
) -> list[Message]:
    "Get all messages for a conversation"
    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(
            Message.sent_at.asc(),
            Message.id.asc(),
        )
    )

    result = await session.scalars(statement)
    return list(result)


async def update_message_content(
    session: AsyncSession,
    db_message_id: int,
    new_content: str,
) -> bool:
    "Update some message's content"
    message = await session.get(
        Message,
        db_message_id,
    )

    if message is None:
        return False

    message.content = new_content
    await session.flush()

    return True


async def delete_message(
    session: AsyncSession,
    db_message_id: int,
) -> bool:
    "Delete a message"
    message = await session.get(
        Message,
        db_message_id,
    )

    if message is None:
        return False

    await session.delete(message)
    await session.flush()

    return True