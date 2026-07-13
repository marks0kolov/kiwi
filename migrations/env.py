import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import DATABASE_URL
from app.db.models import Base


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)  # read logging config for file


config.set_main_option(
    "sqlalchemy.url",
    str(DATABASE_URL).replace("%", "%%"),
)  # override database url

target_metadata = Base.metadata  # read desired schema


def run_migrations_offline() -> None:
    "Run migrations without really doing anything to the real database"
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    "Perform migration using established connection"
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    "Create connection, run migrations offline and actually do run them"
    configuration = config.get_section(
        config.config_ini_section,
        {},
    )

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    "Run run_async_migrations() in async"
    asyncio.run(run_async_migrations())


# run the migrations in different modes depending on context
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()