from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    state: Mapped["State | None"] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    session: Mapped[Session] = relationship(back_populates="messages")


class State(Base):
    __tablename__ = "state"

    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    state_json: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    session: Mapped[Session] = relationship(back_populates="state")
