import asyncio
import random
from datetime import datetime, timezone

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
from app.config import BOT_TOKEN, ADMIN_ID
from app.db.models import MessageType
from app.db.repo import (
    create_conversation,
    create_message,
    get_current_conversation,
    upsert_user,
)
from app.db.session import Session, engine

router = Router()


async def save_kiwi_action(
    conversation_id: int,
    action: KiwiAction,
    message_id: int | None,
    sent_at: datetime,
    context: dict[str, object] | None = None,
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
            sent_at=sent_at,
            context=context,
        )


async def execute_actions(
    message: ttypes.Message,
    conversation_id: int,
    actions: list[KiwiAction],
) -> None:
    """Execute either sending or reacting to a user's message"""
    for i, action in enumerate(actions):
        if isinstance(action, SendAction):
            # send and log message
            sent_message = await message.answer(action.message)
            await save_kiwi_action(
                conversation_id,
                action,
                sent_message.message_id,
                sent_message.date,
            )
            # get wait time
            sec_to_wait = len(action.message) / 7

        elif isinstance(action, ReactAction):
            # send and log reaction
            await message.bot.set_message_reaction(
                chat_id=message.chat.id,
                message_id=action.message_id,
                reaction=[ttypes.ReactionTypeEmoji(emoji=action.reaction)],
            )
            await save_kiwi_action(
                conversation_id,
                action,
                None,
                datetime.now(timezone.utc),
                {"to_id": action.message_id},
            )

            # get wait time
            sec_to_wait = 0.5

        if i < (len(actions) - 1):
            sec_to_wait = random.uniform(
                max(sec_to_wait - 0.5, 0),
                max(sec_to_wait + 0.5, 2.5)
            )
            await asyncio.sleep(sec_to_wait)


@router.message(CommandStart())
async def start_handler(
    message: ttypes.Message,
) -> None:
    """Create a new conversation for user"""
    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
    )

    async with Session.begin() as session:
        await upsert_user(
            session=session,
            user_id=message.from_user.id,
            username=message.from_user.username,
        )
        is_first_conversation = await get_current_conversation(
            session=session,
            user_id=message.from_user.id,
        ) is None
        conversation = await create_conversation(
            session=session,
            user_id=message.from_user.id,
            system_prompt=create_system_prompt(
                mode="private",
                username=username,
            ),
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
                "The user started their first conversation with you. Introduce yourself shortly  and greet them!"
                if is_first_conversation
                else "The user started a new conversation with you, erasing the previous context. Greet them!"
            ),
            sent_at=message.date,
        )
    await execute_actions(message, conversation_id, actions)


@router.message()
async def message_handler(
    message: ttypes.Message,
) -> None:
    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
    )

    # get current conversation
    async with Session.begin() as session:
        await upsert_user(
            session=session,
            user_id=message.from_user.id,
            username=message.from_user.username,
        )
        conversation = await get_current_conversation(
            session=session,
            user_id=message.from_user.id,
        )
        if conversation is None:
            conversation = await create_conversation(
                session=session,
                user_id=message.from_user.id,
                system_prompt=create_system_prompt(
                    mode="private",
                    username=username,
                ),
            )
        conversation_id = conversation.id

    async with ChatActionSender.typing(
        bot=message.bot,
        chat_id=message.chat.id,
    ):  # use the "typing..." indicator
        actions = await ask(
            conversation_id=conversation_id,
            message_type=MessageType.USER_MESSAGE,
            content=message.text,
            message_id=message.message_id,
            sent_at=message.date,
            context=(
                {"reply_to": message.reply_to_message.message_id}
                if message.reply_to_message is not None
                else None
            ),
        )  # get AI's response

        await execute_actions(
            message,
            conversation_id,
            actions,
        )  # execute the actions provided by the AI


async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    try:
        await dp.start_polling(bot)
        await bot.send_message(ADMIN_ID, "✅ bot started")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
