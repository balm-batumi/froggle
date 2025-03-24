import asyncio
import sys
sys.path.append('..')  # Поднимаемся на уровень вверх к корню проекта, где database.py
from database import Base, get_db, Tag
from sqlalchemy import select
from loguru import logger

# Настройка логирования
logger.add("fill_tags.log", rotation="10MB", compression="zip", level="INFO")

async def fill_tags():
    tags_list = [
        "Сдаю",
        "Сниму",
        "Продаю",
        "Студия",
        "Одна спальня",
        "Две+ спальни",
        "Дом",
        "Земля",
        "Коммерция",
        "Новостройка",
        "Куплю",
        "Посуточно"
    ]
    category = "Housing"
    logger.info(f"Начало заполнения таблицы tags для категории '{category}'")
    async for session in get_db():
        for tag_name in tags_list:
            logger.debug(f"Проверка тега: {tag_name}")
            existing_tag = await session.execute(
                select(Tag).where(Tag.name == tag_name, Tag.category == category)
            )
            if not existing_tag.scalar_one_or_none():
                logger.info(f"Добавление нового тега: {tag_name} в категорию {category}")
                new_tag = Tag(name=tag_name, category=category)
                session.add(new_tag)
            else:
                logger.debug(f"Тег уже существует: {tag_name} в категории {category}")
        logger.info("Сохранение изменений в базе данных")
        await session.commit()
    logger.info("Заполнение таблицы tags завершено")

if __name__ == "__main__":
    asyncio.run(fill_tags())