from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

DATABASE_URL = settings.database_url

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def get_db():
    async with async_session() as session:
        yield session
