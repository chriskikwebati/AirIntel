import os

from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()


def normalize_database_url(url):
    # SQLAlchemy only accepts the "postgresql://" scheme, but some hosts hand out "postgres://".
    if url and url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL"))

# pool_pre_ping reconnects if a serverless database (e.g. Neon) dropped an idle connection.
engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False) if engine else None

Base = declarative_base()


def get_db():
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="Alerts database is not configured (DATABASE_URL unset)")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
