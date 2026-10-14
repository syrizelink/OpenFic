from functools import partial, update_wrapper

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from alembic.runtime.migration import RevisionStep

from app.logging import configure_standard_logging

from app.storage.migrations.postgresql_compat import upgrade_dashboard_metadata_indexes

# 导入应用配置和模型
from app.settings import settings, to_sync_database_url
from sqlmodel import SQLModel

# 注册所有表到 SQLModel.metadata 用于 autogenerate
from app.storage.models import *  # noqa: F401, F403
# agent_runtime 中还有部分模型未包含在 app.storage.models 中
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


def _migration_steps(migration_fn, revisions, migration_context):
    for step in migration_fn(revisions, migration_context):
        if (
            migration_context.dialect.name == "postgresql"
            and isinstance(step, RevisionStep)
            and step.is_upgrade
            and step.to_revisions == ("1027",)
        ):
            # Keep published scripts immutable and replace only this execution step.
            step.migration_fn = update_wrapper(
                partial(upgrade_dashboard_metadata_indexes, step.revision.module),
                step.migration_fn,
            )
        yield step


def _configure_context(**options) -> None:
    context.configure(**options)
    migration_fn = context.get_context().opts["fn"]
    context.configure(**options, fn=partial(_migration_steps, migration_fn))


configure_standard_logging()

# 配置数据库 URL。迁移工具可通过 Config.attributes 显式覆盖默认主库。
database_url = (
    config.attributes.get("openfic_database_url") or settings.database_sync_url
)
config.set_main_option(
    "sqlalchemy.url", to_sync_database_url(database_url).replace("%", "%%")
)

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
    _configure_context(
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
    connection = config.attributes.get("openfic_connection")
    if connection is not None:
        _configure_context(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _configure_context(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
