import asyncio
import sys
sys.path.append('..')
from database import Base, get_db, City
from sqlalchemy import select
from loguru import logger


async def fill_cities():
    cities_list = [
        "Тбилиси",
        "Кутаиси",
        "Батуми",
        "Рустави",
        "Гори",
        "Зугдиди",
        "Поти",
        "Телави",
        "Ахалцихе",
        "Озургети",
        "Мцхета",
        "Кобулети",
        "Зестафони",
        "Марнеули",
        "Амбролаури"
    ]
    logger.info("Начало заполнения таблицы cities")
    async for session in get_db():
        for city_name in cities_list:
            logger.debug(f"Проверка города: {city_name}")
            existing_city = await session.execute(
                select(City).where(City.name == city_name)
            )
            if not existing_city.scalar_one_or_none():
                logger.info(f"Добавление нового города: {city_name}")
                new_city = City(name=city_name)
                session.add(new_city)
            else:
                logger.debug(f"Город уже существует: {city_name}")
        logger.info("Сохранение изменений в базе данных")
        await session.commit()
    logger.info("Заполнение таблицы cities завершено")


if __name__ == "__main__":
    asyncio.run(fill_cities())