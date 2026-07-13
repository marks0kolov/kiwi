from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from config import DATABASE_URL


engine = create_async_engine(
    DATABASE_URL,
    echo=True,
)

Session = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)