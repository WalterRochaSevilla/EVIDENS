from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.async_database_url,
    pool_pre_ping=True,
)

SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Clase padre de la que heredarán todas las tablas del modelo de datos."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Entrega una sesión de base de datos por petición y la cierra al terminar."""
    async with SessionFactory() as session:
        yield session