from logging.config import fileConfig
import os
import sys

from alembic import context
from sqlalchemy import Column, MetaData, String, Table, engine_from_config, inspect, pool

# add app path
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../')

from app import models  # noqa: E402
from app.config import settings  # noqa: E402

config = context.config

# Override URL from settings
if settings.database_url:
    config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = models.Base.metadata


ALEMBIC_VERSION_NUM_LENGTH = 255
ALTER_VERSION_NUM_SQL = (
    'ALTER TABLE alembic_version '
    f'ALTER COLUMN version_num TYPE VARCHAR({ALEMBIC_VERSION_NUM_LENGTH})'
)


def _create_alembic_version_table(connection):
    metadata = MetaData()
    Table(
        "alembic_version",
        metadata,
        Column(
            "version_num",
            String(ALEMBIC_VERSION_NUM_LENGTH),
            primary_key=True,
            nullable=False,
        ),
    )
    metadata.create_all(connection)


def _version_column(columns):
    return next((column for column in columns if column.get("name") == "version_num"), None)


def _version_length_needs_update(version_col) -> bool:
    if version_col is None:
        return False
    col_type = version_col.get("type")
    length = getattr(col_type, "length", None)
    return length is not None and length < ALEMBIC_VERSION_NUM_LENGTH


def _alter_version_num_column(connection) -> None:
    if connection.dialect.name == "postgresql":
        connection.exec_driver_sql(ALTER_VERSION_NUM_SQL)
        return

    try:
        connection.exec_driver_sql(ALTER_VERSION_NUM_SQL)
    except Exception:
        return


def ensure_alembic_version_table(connection):
    inspector = inspect(connection)

    if "alembic_version" not in inspector.get_table_names():
        _create_alembic_version_table(connection)
        return

    if not _version_length_needs_update(_version_column(inspector.get_columns("alembic_version"))):
        return

    _alter_version_num_column(connection)


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        with connection.begin():
            ensure_alembic_version_table(connection)
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
