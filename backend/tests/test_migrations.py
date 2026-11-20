from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app import db as database
from app import main, models
from app.db import Base
from app.migrate import alembic_config


def test_migrations_create_the_same_tables_as_the_models(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(alembic_config(), "head")

    inspector = inspect(create_engine(url))
    for table in Base.metadata.sorted_tables:
        migrated = {c["name"] for c in inspector.get_columns(table.name)}
        assert migrated == {c.name for c in table.columns}, table.name


def test_migrations_adopt_an_existing_devices_table(tmp_path, monkeypatch):
    """The live database already had `devices` before migrations existed; it must keep its data."""
    url = f"sqlite:///{tmp_path / 'existing.db'}"
    engine = create_engine(url)
    models.Device.__table__.create(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO devices (push_token, lat, lon) VALUES ('ExponentPushToken[x]', 1, 2)"))

    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(alembic_config(), "head")

    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM devices")).scalar() == 1
    assert inspect(engine).has_table("alert_history")


def test_migrations_downgrade_cleanly(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'down.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(alembic_config(), "head")
    command.downgrade(alembic_config(), "base")
    assert not inspect(create_engine(url)).has_table("alert_history")


def test_app_applies_migrations_on_startup(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'startup.db'}"
    engine = create_engine(url)
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setattr(database, "engine", engine)

    with TestClient(main.app) as client:  # entering the client runs the startup hook
        assert client.get("/healthz").status_code == 200

    assert inspect(engine).has_table("alert_history")
