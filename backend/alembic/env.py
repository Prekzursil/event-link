from logging.config import fileConfig
import os
import sys

from alembic import context
from sqlalchemy import Column, MetaData, String, Table, engine_from_config, inspect, pool, text

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


def ensure_alembic_version_table(connection):
    inspector = inspect(connection)

    if "alembic_version" not in inspector.get_table_names():
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
        return

    columns = inspector.get_columns("alembic_version")
    version_col = next(
        (column for column in columns if column.get("name") == "version_num"),
        None,
    )
    if version_col is None:
        return

    col_type = version_col.get("type")
    length = getattr(col_type, "length", None)
    if length is None or length >= ALEMBIC_VERSION_NUM_LENGTH:
        return

    if connection.dialect.name == "postgresql":
        connection.execute(
            text(
                "ALTER TABLE alembic_version "
                f"ALTER COLUMN version_num TYPE VARCHAR({ALEMBIC_VERSION_NUM_LENGTH})"
            )
        )
        return

    try:
        connection.execute(
            text(
                "ALTER TABLE alembic_version "
                f"ALTER COLUMN version_num TYPE VARCHAR({ALEMBIC_VERSION_NUM_LENGTH})"
            )
        )
    except Exception:
        return


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
