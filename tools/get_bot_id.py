import asyncio
from aiogram import Bot
from config import BOT_TOKEN_AD

async def get_bot_id():
    bot = Bot(token=BOT_TOKEN_AD)
    try:
        me = await bot.get_me()
        print(f"Telegram ID бота-сендера: {me.id}")
        print(f"Username: @{me.username}")
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(get_bot_id())