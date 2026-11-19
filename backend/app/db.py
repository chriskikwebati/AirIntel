import os

from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    # SQLAlchemy only accepts the "postgresql://" scheme some hosts don't use.
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

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
