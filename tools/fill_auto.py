import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal, Tag
from loguru import logger

# Список тегов для категории "auto" (захардкожены)
AUTO_TAGS = [
    # Ключевые теги (is_primary=True)
    {"name": "продаю", "category": "auto", "is_primary": True, "order": 1},
    {"name": "куплю", "category": "auto", "is_primary": True, "order": 2},
    {"name": "ремонт", "category": "auto", "is_primary": True, "order": 3},
    {"name": "запчасти", "category": "auto", "is_primary": True, "order": 4},
    {"name": "аренда", "category": "auto", "is_primary": True, "order": 5},
    # Регулярные теги (is_primary=False)
    {"name": "внедорожник", "category": "auto", "is_primary": False, "order": 6},
    {"name": "электричка", "category": "auto", "is_primary": False, "order": 7},
    {"name": "седан", "category": "auto", "is_primary": False, "order": 8},
    {"name": "грузовик", "category": "auto", "is_primary": False, "order": 9},
    {"name": "мотоцикл", "category": "auto", "is_primary": False, "order": 10},
    {"name": "гибрид", "category": "auto", "is_primary": False, "order": 11},
    {"name": "кузовщина", "category": "auto", "is_primary": False, "order": 12},
    {"name": "двигатель", "category": "auto", "is_primary": False, "order": 13},
    {"name": "ходовая", "category": "auto", "is_primary": False, "order": 14},
    {"name": "электрика", "category": "auto", "is_primary": False, "order": 15},
    {"name": "тюнинг", "category": "auto", "is_primary": False, "order": 16},
    {"name": "коммерческий транспорт", "category": "auto", "is_primary": False, "order": 17},
    {"name": "аксессуары", "category": "auto", "is_primary": False, "order": 18},
    {"name": "битый", "category": "auto", "is_primary": False, "order": 19},
    {"name": "новый", "category": "auto", "is_primary": False, "order": 20},
    {"name": "б/у", "category": "auto", "is_primary": False, "order": 21},
]

async def fill_auto_tags():
    """Заполняет таблицу tags тегами для категории 'auto'."""
    logger.info("Начало заполнения таблицы tags для категории 'auto'")
    async with AsyncSessionLocal() as session:  # noqa
        try:
            for tag_data in AUTO_TAGS:
                tag = Tag(
                    name=tag_data["name"],
                    category=tag_data["category"],
                    is_primary=tag_data["is_primary"],
                    order=tag_data["order"]
                )
                session.add(tag)
                logger.debug(f"Добавлен тег: {tag.name} (order={tag.order}, is_primary={tag.is_primary})")
            await session.commit()
            logger.info(f"Успешно добавлено {len(AUTO_TAGS)} тегов в таблицу tags")
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при заполнении таблицы tags: {e}")
            raise

async def main():
    """Основная функция для запуска заполнения тегов."""
    await fill_auto_tags()

if __name__ == "__main__":
    asyncio.run(main())