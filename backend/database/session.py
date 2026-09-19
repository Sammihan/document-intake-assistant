from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker


DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "document_intake.db"
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[OrmSession, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
