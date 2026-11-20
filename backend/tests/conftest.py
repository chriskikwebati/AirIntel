import os

# Tests must never touch a real database. An empty value (rather than unsetting it) stops
# load_dotenv() from filling it in from a local .env file.
os.environ["DATABASE_URL"] = ""

import pytest  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import main  # noqa: E402
from app.db import Base, get_db  # noqa: E402

VALID_TOKEN = "ExponentPushToken[abc123]"


@pytest.fixture(autouse=True)
def reset_rate_limits():
    main.limiter.reset()
    yield


@pytest.fixture
def db_session():
    """A fresh in-memory SQLite database with all tables, wired into the API."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()

    def override_get_db():
        yield session

    main.app.dependency_overrides[get_db] = override_get_db
    yield session
    main.app.dependency_overrides.pop(get_db, None)
    session.close()
    engine.dispose()
