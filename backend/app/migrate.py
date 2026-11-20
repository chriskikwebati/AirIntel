from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parent.parent


def alembic_config():
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def upgrade_database():
    """Apply any pending migrations. Safe to run on every startup: it does nothing when up to date."""
    config = alembic_config()
    # Keep the app's JSON logging instead of letting alembic.ini replace it.
    config.attributes["configure_logging"] = False
    command.upgrade(config, "head")
