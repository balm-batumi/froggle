from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, ARRAY, select
from sqlalchemy.sql import func
from loguru import logger
from config import DATABASE_URL

# Создание асинхронного движка для подключения к базе данных
engine = create_async_engine(DATABASE_URL, echo=False)

# Создание асинхронной сессии
AsyncSessionLocal = sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)

# Базовый класс для моделей
Base = declarative_base()

# Генератор сессий базы данных
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Модель User
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    username = Column(String)
    city = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)

# Модель Advertisement
class Advertisement(Base):
    __tablename__ = "advertisements"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    category = Column(String)
    city = Column(String, nullable=True)
    tags = Column(ARRAY(String), nullable=True)
    title_ru = Column(String)
    description_ru = Column(String)
    price = Column(String(30), nullable=True)
    media_file_ids = Column(ARRAY(String), nullable=True)
    contact_info = Column(String, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=func.now())


class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    is_primary = Column(Boolean, default=False)  # Новый столбец для обязательных тегов

# Модель City
class City(Base):
    __tablename__ = "cities"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

class Favorite(Base):
    __tablename__ = "favorites"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    advertisement_id = Column(Integer, ForeignKey("advertisements.id"), nullable=False)
    added_at = Column(DateTime, default=func.now())


async def add_to_favorites(user_id: int, advertisement_id: int) -> int:
    """Добавление объявления в избранное"""
    async with AsyncSessionLocal() as session:
        favorite = Favorite(user_id=user_id, advertisement_id=advertisement_id)
        session.add(favorite)
        await session.commit()
        await session.refresh(favorite)
        return favorite.id

async def remove_from_favorites(user_id: int, advertisement_id: int) -> bool:
    """Удаление объявления из избранного"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.advertisement_id == advertisement_id
            )
        )
        favorite = result.scalar_one_or_none()
        if favorite:
            await session.delete(favorite)
            await session.commit()
            return True
        return False

async def is_favorite(user_id: int, advertisement_id: int) -> bool:
    """Проверка, есть ли объявление в избранном"""
    async for session in get_db():
        result = await session.execute(
            select(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.advertisement_id == advertisement_id
            )
        )
        return result.scalar_one_or_none() is not None



# Функция добавления объявления в базу данных с учетом цены
async def add_advertisement(user_id: int, category: str, city: str, title_ru: str, description_ru: str, tags: list[str], media_file_ids: list[str], contact_info: str, price: str = None) -> int:
    async with AsyncSessionLocal() as session:
        ad = Advertisement(
            user_id=user_id,
            category=category,
            city=city,
            title_ru=title_ru,
            description_ru=description_ru,
            tags=tags,
            media_file_ids=media_file_ids,
            contact_info=contact_info,
            price=price  # Добавляем цену
        )
        session.add(ad)
        await session.commit()
        await session.refresh(ad)
        return ad.id


# Функция получения тегов для категории
async def get_category_tags(category: str):
    async for session in get_db():
        result = await session.execute(select(Tag).where(Tag.category == category))
        tags = result.scalars().all()
        return [(tag.id, tag.name) for tag in tags]

# Функция получения списка городов
async def get_cities():
    async for session in get_db():
        result = await session.execute(select(City))
        cities = result.scalars().all()
        return [(city.id, city.name) for city in cities]

# Инициализация базы данных
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("База данных Froggle_db инициализирована")