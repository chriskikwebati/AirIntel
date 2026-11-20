import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine

from app.db import Base, normalize_database_url
from app import models  # noqa: F401  (registers the tables on Base.metadata)

load_dotenv()

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def database_url():
    url = normalize_database_url(os.getenv("DATABASE_URL"))
    if not url:
        raise RuntimeError("DATABASE_URL is not set; nothing to migrate")
    return url


def run_migrations_offline():
    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = create_engine(database_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
