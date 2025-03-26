from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from loguru import logger
import asyncio
import aiohttp

class NetworkErrorMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        try:
            return await handler(event, data)
        except aiohttp.ClientOSError as e:
            logger.exception(
                f"Network error caught: {str(e)}\n"
                f"Event: {event.__class__.__name__}\n"
                f"Bot ID: {data['bot'].id}\n"
                f"Update ID: {event.update_id if hasattr(event, 'update_id') else 'N/A'}"
            )
            # Продолжаем выполнение, чтобы не прерывать polling
            await asyncio.sleep(1)  # Ждем 1 секунду перед повторной попыткой
            return None
        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            raise  # Пробрасываем другие ошибки дальше