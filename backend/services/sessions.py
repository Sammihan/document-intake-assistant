from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from backend.llm.gemini import LLMService
from backend.models.database import Message, Session, State
from backend.schemas.state import PersonalWishesState
from backend.services.document_generator import generate_document
from backend.services.followups import compose_assistant_message
from backend.services.state_updates import StateUpdateConflictError, apply_extracted_fields


class SessionNotFoundError(Exception):
    pass


def create_session(db: OrmSession) -> Session:
    state = PersonalWishesState()
    session = Session()
    db.add(session)
    db.flush()
    db.add(State(session_id=session.id, state_json=state.model_dump_json(), version=1))
    db.commit()
    db.refresh(session)
    return session


def get_session(db: OrmSession, session_id: int) -> Session:
    session = db.get(Session, session_id)
    if session is None:
        raise SessionNotFoundError
    return session


def get_state(db: OrmSession, session_id: int) -> PersonalWishesState:
    session = get_session(db, session_id)
    if session.state is None:
        raise SessionNotFoundError
    return PersonalWishesState.model_validate_json(session.state.state_json)


def get_messages(db: OrmSession, session_id: int) -> list[Message]:
    get_session(db, session_id)
    return list(
        db.scalars(
            select(Message).where(Message.session_id == session_id).order_by(Message.created_at, Message.id)
        ).all()
    )


def get_document(db: OrmSession, session_id: int) -> Path:
    state = get_state(db, session_id)
    return generate_document(state, session_id=session_id)


def persist_message_exchange(
    db: OrmSession,
    session_id: int,
    user_message: str,
    *,
    llm_service: LLMService,
) -> tuple[str, PersonalWishesState]:
    state = get_state(db, session_id)
    history = get_messages(db, session_id)
    user_record = Message(session_id=session_id, role="user", content=user_message)
    db.add(user_record)
    db.commit()

    llm_response = llm_service.extract(
        current_state=state,
        messages=history,
        user_message=user_message,
    )

    try:
        updated_state = apply_extracted_fields(
            state,
            llm_response.extracted_fields,
            user_message=user_message,
        )
        assistant_message = compose_assistant_message(
            llm_message=llm_response.assistant_message,
            updated_state=updated_state,
            needs_clarification=llm_response.needs_clarification,
            latest_user_message=user_message,
        )
    except StateUpdateConflictError as exc:
        updated_state = state
        assistant_message = (
            f"I noticed a conflict with your previously confirmed information: {exc}. "
            "Please clarify or let me know if you would like to update this."
        )

    assistant_record = Message(
        session_id=session_id,
        role="assistant",
        content=assistant_message,
    )
    try:
        persisted_state = db.get(State, session_id)
        if persisted_state is None:
            raise SessionNotFoundError

        if updated_state != state:
            persisted_state.state_json = updated_state.model_dump_json()
            persisted_state.version += 1

        db.add(assistant_record)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return assistant_message, updated_state
