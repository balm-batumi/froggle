import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal, Tag
from loguru import logger

# Список тегов для категории "shopping" (захардкожены)
SHOP_TAGS = [
    # Ключевые теги (is_primary=True)
    {"name": "одежда", "category": "shopping", "is_primary": True, "order": 1},
    {"name": "техника", "category": "shopping", "is_primary": True, "order": 2},
    {"name": "для дома", "category": "shopping", "is_primary": True, "order": 3},
    {"name": "красота/здоровье/спорт", "category": "shopping", "is_primary": True, "order": 4},
    {"name": "детям", "category": "shopping", "is_primary": True, "order": 5},
    {"name": "животным", "category": "shopping", "is_primary": True, "order": 6},
    {"name": "всячина", "category": "shopping", "is_primary": True, "order": 7},
    # Регулярные теги (is_primary=False)
    {"name": "гаджеты", "category": "shopping", "is_primary": False, "order": 8},
    {"name": "для ремонта", "category": "shopping", "is_primary": False, "order": 9},
    {"name": "обувь", "category": "shopping", "is_primary": False, "order": 10},
    {"name": "интерьер", "category": "shopping", "is_primary": False, "order": 11},
    {"name": "сантехника", "category": "shopping", "is_primary": False, "order": 12},
    {"name": "бытовая техника", "category": "shopping", "is_primary": False, "order": 13},
    {"name": "сад", "category": "shopping", "is_primary": False, "order": 14},
    {"name": "хозтовары", "category": "shopping", "is_primary": False, "order": 15},
    {"name": "электроника", "category": "shopping", "is_primary": False, "order": 16},
    {"name": "хобби", "category": "shopping", "is_primary": False, "order": 17},
    {"name": "взрослые", "category": "shopping", "is_primary": False, "order": 18},
    {"name": "косметика", "category": "shopping", "is_primary": False, "order": 19},
    {"name": "туризм", "category": "shopping", "is_primary": False, "order": 20},
    {"name": "аптека", "category": "shopping", "is_primary": False, "order": 21},
    {"name": "аксессуары", "category": "shopping", "is_primary": False, "order": 22},
]

async def fill_shop_tags():
    """Заполняет таблицу tags тегами для категории 'shopping'."""
    logger.info("Начало заполнения таблицы tags для категории 'shopping'")
    async with AsyncSessionLocal() as session:  # noqa
        try:
            for tag_data in SHOP_TAGS:
                tag = Tag(
                    name=tag_data["name"],
                    category=tag_data["category"],
                    is_primary=tag_data["is_primary"],
                    order=tag_data["order"]
                )
                session.add(tag)
                logger.debug(f"Добавлен тег: {tag.name} (order={tag.order}, is_primary={tag.is_primary})")
            await session.commit()
            logger.info(f"Успешно добавлено {len(SHOP_TAGS)} тегов в таблицу tags")
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при заполнении таблицы tags: {e}")
            raise

async def main():
    """Основная функция для запуска заполнения тегов."""
    await fill_shop_tags()

if __name__ == "__main__":
    asyncio.run(main())