from sqlalchemy.engine import Engine

from backend.database.base import Base
from backend.database.session import engine as default_engine
from backend.models.database import Message, Session, State  # noqa: F401


def init_db(engine: Engine | None = None) -> None:
    """Create database tables for the configured SQLAlchemy models."""
    Base.metadata.create_all(bind=engine or default_engine)
