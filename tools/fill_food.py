import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal, Tag
from loguru import logger

# Список тегов для категории "food" (захардкожены)
FOOD_TAGS = [
    # Ключевые теги (is_primary=True)
    {"name": "ресторан", "category": "food", "is_primary": True, "order": 1},
    {"name": "кафе", "category": "food", "is_primary": True, "order": 2},
    {"name": "фастфуд", "category": "food", "is_primary": True, "order": 3},
    {"name": "домашняя кухня", "category": "food", "is_primary": True, "order": 4},
    {"name": "продукты", "category": "food", "is_primary": True, "order": 5},
    {"name": "кондитерская", "category": "food", "is_primary": True, "order": 6},
    # Регулярные теги (is_primary=False)
    {"name": "доставка", "category": "food", "is_primary": False, "order": 7},
    {"name": "грузинская", "category": "food", "is_primary": False, "order": 8},
    {"name": "итальянская", "category": "food", "is_primary": False, "order": 9},
    {"name": "японская", "category": "food", "is_primary": False, "order": 10},
    {"name": "вегетарианская", "category": "food", "is_primary": False, "order": 11},
    {"name": "завтраки", "category": "food", "is_primary": False, "order": 12},
    {"name": "центр", "category": "food", "is_primary": False, "order": 13},
    {"name": "вид", "category": "food", "is_primary": False, "order": 14},
    {"name": "уют", "category": "food", "is_primary": False, "order": 15},
    {"name": "бизнес-ланч", "category": "food", "is_primary": False, "order": 16},
    {"name": "pet-friendly", "category": "food", "is_primary": False, "order": 17},
    {"name": "стейки", "category": "food", "is_primary": False, "order": 18},
]

async def fill_food_tags():
    """Заполняет таблицу tags тегами для категории 'food'."""
    logger.info("Начало заполнения таблицы tags для категории 'food'")
    async with AsyncSessionLocal() as session:  # noqa
        try:
            for tag_data in FOOD_TAGS:
                tag = Tag(
                    name=tag_data["name"],
                    category=tag_data["category"],
                    is_primary=tag_data["is_primary"],
                    order=tag_data["order"]
                )
                session.add(tag)
                logger.debug(f"Добавлен тег: {tag.name} (order={tag.order}, is_primary={tag.is_primary})")
            await session.commit()
            logger.info(f"Успешно добавлено {len(FOOD_TAGS)} тегов в таблицу tags")
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при заполнении таблицы tags: {e}")
            raise

async def main():
    """Основная функция для запуска заполнения тегов."""
    await fill_food_tags()

if __name__ == "__main__":
    asyncio.run(main())