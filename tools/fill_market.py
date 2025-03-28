import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal, Tag
from loguru import logger

# Список тегов для категории "market" (захардкожены, без тега "авто")
MARKET_TAGS = [
    # Ключевые теги (is_primary=True)
    {"name": "продам", "category": "market", "is_primary": True, "order": 1},
    {"name": "куплю", "category": "market", "is_primary": True, "order": 2},
    {"name": "обмен", "category": "market", "is_primary": True, "order": 3},
    {"name": "даром", "category": "market", "is_primary": True, "order": 4},
    # Регулярные теги (is_primary=False)
    {"name": "одежда", "category": "market", "is_primary": False, "order": 5},
    {"name": "техника", "category": "market", "is_primary": False, "order": 6},
    {"name": "электроника", "category": "market", "is_primary": False, "order": 7},
    {"name": "интерьер", "category": "market", "is_primary": False, "order": 8},
    {"name": "детское", "category": "market", "is_primary": False, "order": 9},
    {"name": "спорт", "category": "market", "is_primary": False, "order": 10},
    {"name": "инструменты", "category": "market", "is_primary": False, "order": 11},
    {"name": "хозтовары", "category": "market", "is_primary": False, "order": 12},
    {"name": "посуда", "category": "market", "is_primary": False, "order": 13},
    {"name": "сад", "category": "market", "is_primary": False, "order": 14},
    {"name": "животные", "category": "market", "is_primary": False, "order": 15},
    {"name": "торг уместен", "category": "market", "is_primary": False, "order": 16},
    {"name": "срочно", "category": "market", "is_primary": False, "order": 17},
    {"name": "новое", "category": "market", "is_primary": False, "order": 18},
    {"name": "б/у", "category": "market", "is_primary": False, "order": 19},
    {"name": "винтаж", "category": "market", "is_primary": False, "order": 20},
    {"name": "творчество", "category": "market", "is_primary": False, "order": 21},
    {"name": "хобби", "category": "market", "is_primary": False, "order": 22},
    {"name": "аксессуары", "category": "market", "is_primary": False, "order": 23},
]

async def fill_market_tags():
    """Заполняет таблицу tags тегами для категории 'market'."""
    logger.info("Начало заполнения таблицы tags для категории 'market'")
    async with AsyncSessionLocal() as session:  # noqa
        try:
            for tag_data in MARKET_TAGS:
                tag = Tag(
                    name=tag_data["name"],
                    category=tag_data["category"],
                    is_primary=tag_data["is_primary"],
                    order=tag_data["order"]
                )
                session.add(tag)
                logger.debug(f"Добавлен тег: {tag.name} (order={tag.order}, is_primary={tag.is_primary})")
            await session.commit()
            logger.info(f"Успешно добавлено {len(MARKET_TAGS)} тегов в таблицу tags")
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при заполнении таблицы tags: {e}")
            raise

async def main():
    """Основная функция для запуска заполнения тегов."""
    await fill_market_tags()

if __name__ == "__main__":
    asyncio.run(main())