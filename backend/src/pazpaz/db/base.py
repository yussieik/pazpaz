"""SQLAlchemy base configuration."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from pazpaz.core.config import settings


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """Dependency for database sessions."""
    async with AsyncSessionLocal() as session:
        yield session
