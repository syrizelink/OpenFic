from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.logging import configure_standard_logging
# Mengimpor konfigurasi aplikasi dan model
from app.settings import settings
from sqlmodel import SQLModel

# Mendaftarkan semua tabel ke SQLModel.metadata untuk autogenerate
from app.storage.models import *  # noqa: F401, F403
# Sebagian model di agent_runtime belum termasuk dalam app.storage.models
from app.agent_runtime.persistence.model import (  # noqa: F401, F403
    AgentChildRun,
    AgentChildRunRequest,
    AgentDefinitionRecord,
    PlanRecord,
    PlanTodoRecord,
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

configure_standard_logging()

# Mengonfigurasi URL basis data (diambil dari setelan aplikasi, tetapi memakai URL sinkron)
database_url = settings.database_url.replace("+aiosqlite", "")
config.set_main_option("sqlalchemy.url", database_url)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
