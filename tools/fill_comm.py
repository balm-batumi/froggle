import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal, Tag
from loguru import logger

# Список тегов для категории "communication" (захардкожены)
COMM_TAGS = [
    # Ключевые теги (is_primary=True)
    {"name": "знакомства", "category": "communication", "is_primary": True, "order": 1},
    {"name": "деловое", "category": "communication", "is_primary": True, "order": 2},
    {"name": "по интересам", "category": "communication", "is_primary": True, "order": 3},
    {"name": "мероприятия", "category": "communication", "is_primary": True, "order": 4},
    # Регулярные теги (is_primary=False)
    {"name": "дружба", "category": "communication", "is_primary": False, "order": 5},
    {"name": "онлайн", "category": "communication", "is_primary": False, "order": 6},
    {"name": "попутчики", "category": "communication", "is_primary": False, "order": 7},
    {"name": "путешествия", "category": "communication", "is_primary": False, "order": 8},
    {"name": "чаты", "category": "communication", "is_primary": False, "order": 9},
    {"name": "нетворкинг", "category": "communication", "is_primary": False, "order": 10},
    {"name": "совет и помощь", "category": "communication", "is_primary": False, "order": 11},
    {"name": "отношения", "category": "communication", "is_primary": False, "order": 12},
    {"name": "игры", "category": "communication", "is_primary": False, "order": 13},
    {"name": "местные", "category": "communication", "is_primary": False, "order": 14},
]

async def fill_comm_tags():
    """Заполняет таблицу tags тегами для категории 'communication'."""
    logger.info("Начало заполнения таблицы tags для категории 'communication'")
    async with AsyncSessionLocal() as session:  # noqa
        try:
            for tag_data in COMM_TAGS:
                tag = Tag(
                    name=tag_data["name"],
                    category=tag_data["category"],
                    is_primary=tag_data["is_primary"],
                    order=tag_data["order"]
                )
                session.add(tag)
                logger.debug(f"Добавлен тег: {tag.name} (order={tag.order}, is_primary={tag.is_primary})")
            await session.commit()
            logger.info(f"Успешно добавлено {len(COMM_TAGS)} тегов в таблицу tags")
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при заполнении таблицы tags: {e}")
            raise

async def main():
    """Основная функция для запуска заполнения тегов."""
    await fill_comm_tags()

if __name__ == "__main__":
    asyncio.run(main())