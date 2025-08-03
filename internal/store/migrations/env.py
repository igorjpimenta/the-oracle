from logging.config import fileConfig
import sys
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy.engine.url import URL

from alembic import context

from app.core.config.settings import get_database_settings
from app.core.database.schema import Base

# Add the directory to the Python path
backend_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_root))

# Import our database schema

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
settings = get_database_settings()

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate support
target_metadata = Base.metadata

# Tables to exclude from migrations (managed by the application itself)
EXCLUDED_TABLES: set[str] = set()


def include_object(object, name, type_, reflected, compare_to):
    """
    Should we include this object in the migration?

    Args:
        object: The schema object (table, column, etc.)
        name: The name of the object
        type_: The type of object ('table', 'column', 'index', etc.)
        reflected: True if the object was reflected from the database
        compare_to: The object being compared to (if any)

    Returns:
        False if the object should be excluded from migrations, True otherwise
    """
    if type_ == "table" and name in EXCLUDED_TABLES:
        return False

    return True

# Get database URL from environment variables


def get_database_url() -> URL:
    """Get database URL from settings for migrations"""
    # Use the sync URL object which already has SSL configured
    return settings.database_url_obj


def get_database_url_str() -> str:
    """Get database URL from settings for migrations"""
    url = get_database_url()
    return url.render_as_string(hide_password=False)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Override the sqlalchemy.url in config
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_database_url_str()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
