import asyncio
import random

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram import types as ttypes
from aiogram.utils.chat_action import ChatActionSender

from app.ai import (
    KiwiAction,
    ReactAction,
    SendAction,
    ask,
    create_system_prompt,
)
from app.config import BOT_TOKEN
from app.db.models import MessageType
from app.db.repo import (
    create_conversation,
    create_message,
    get_current_conversation,
)
from app.db.session import Session, engine

router = Router()


async def save_kiwi_action(
    conversation_id: int,
    action: KiwiAction,
    message_id: int,
) -> None:
    """Save an action kiwi did into the database"""
    async with Session.begin() as session:
        await create_message(
            session=session,
            conversation_id=conversation_id,
            message_type=(
                MessageType.KIWI_MESSAGE
                if isinstance(action, SendAction)
                else MessageType.KIWI_REACTION
            ),
            content=(
                action.message
                if isinstance(action, SendAction)
                else action.reaction
            ),
            message_id=message_id,
        )


async def execute_actions(
    message: ttypes.Message,
    conversation_id: int,
    actions: list[KiwiAction],
) -> None:
    """Execute either sending or reacting to a user's message"""
    for action in actions:
        if isinstance(action, SendAction):
            sent_message = await message.answer(action.message)
            await save_kiwi_action(
                conversation_id,
                action,
                sent_message.message_id,
            )
        elif isinstance(action, ReactAction):
            await message.bot.set_message_reaction(
                chat_id=message.chat.id,
                message_id=action.message_id,
                reaction=[ttypes.ReactionTypeEmoji(emoji=action.reaction)],
            )
            await save_kiwi_action(
                conversation_id,
                action,
                action.message_id,
            )


@router.message(CommandStart())
async def start_handler(
    message: ttypes.Message,
) -> None:
    """Create a new conversation for user"""
    async with Session.begin() as session:
        is_first_conversation = await get_current_conversation(
            session=session,
            user_id=message.from_user.id,
        ) is None
        conversation = await create_conversation(
            session=session,
            user_id=message.from_user.id,
            system_prompt=create_system_prompt("private"),
        )
        conversation_id = conversation.id

    async with ChatActionSender.typing(
        bot=message.bot,
        chat_id=message.chat.id,
    ):
        actions = await ask(
            conversation_id=conversation_id,
            message_type=MessageType.USER_ACTION,
            content=(
                "The user started their first conversation with you. Greet them and be friendly!"
                if is_first_conversation
                else "The user started a new conversation with you, erasing the previous context."
            ),
        )
    await execute_actions(message, conversation_id, actions)


@router.message()
async def message_handler(
    message: ttypes.Message,
) -> None:
    async with Session.begin() as session:
        conversation = await get_current_conversation(
            session=session,
            user_id=message.from_user.id,
        )
        if conversation is None:
            conversation = await create_conversation(
                session=session,
                user_id=message.from_user.id,
                system_prompt=create_system_prompt("private"),
            )
        conversation_id = conversation.id

    async with ChatActionSender.typing(
        bot=message.bot,
        chat_id=message.chat.id,
    ):
        actions = await ask(
            conversation_id=conversation_id,
            message_type=MessageType.USER_MESSAGE,
            content=message.text,
            message_id=message.message_id,
        )
    await execute_actions(message, conversation_id, actions)


async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    try:
        await dp.start_polling(bot)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
