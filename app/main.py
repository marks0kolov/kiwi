import asyncio

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram import types as ttypes

from config import BOT_TOKEN
from app.ai import ask
from app.db.repo import (
    create_conversation,
    create_message,
    get_current_conversation,
    get_messages
)
from app.db.session import Session, engine

TOKEN = BOT_TOKEN

router = Router()


@router.message(CommandStart())
async def start_handler(
    message: ttypes.Message,
) -> None:
    # basically filler code: much more will be here later
    if message.from_user is None:
        return

    async with Session.begin() as session:
        conversation = await create_conversation(
            session=session,
            user_id=message.from_user.id,
        )

        conversation_id = conversation.id

    await message.answer(
        f"New conversation started: {conversation_id}"
    )


async def main() -> None:
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    try:
        await dp.start_polling(bot)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())