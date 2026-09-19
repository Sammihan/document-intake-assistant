from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as OrmSession

from backend.database.session import get_db
from backend.llm.gemini import GeminiClient, GeminiServiceError, LLMService, MissingGeminiConfigurationError
from backend.schemas.api import (
    CreateSessionResponse,
    HealthResponse,
    MessageResponse,
    SendMessageRequest,
    SendMessageResponse,
)
from backend.schemas.state import PersonalWishesState
from backend.services.sessions import (
    SessionNotFoundError,
    create_session,
    get_document,
    get_messages,
    get_state,
    persist_message_exchange,
)

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

router = APIRouter()


def parse_session_id(session_id: str) -> int:
    try:
        return int(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found") from exc


DbSession = Annotated[OrmSession, Depends(get_db)]
SessionId = Annotated[str, Path(min_length=1)]


def get_llm_service() -> LLMService:
    try:
        return GeminiClient()
    except MissingGeminiConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service is not configured",
        ) from exc


LlmService = Annotated[LLMService, Depends(get_llm_service)]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/sessions", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
def create_new_session(db: DbSession) -> CreateSessionResponse:
    session = create_session(db)
    return CreateSessionResponse(session_id=str(session.id))


@router.get("/sessions/{session_id}/state", response_model=PersonalWishesState)
def read_session_state(session_id: SessionId, db: DbSession) -> PersonalWishesState:
    try:
        return get_state(db, parse_session_id(session_id))
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found") from exc


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
def read_session_messages(session_id: SessionId, db: DbSession) -> list[MessageResponse]:
    try:
        messages = get_messages(db, parse_session_id(session_id))
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found") from exc
    return [
        MessageResponse(role=message.role, content=message.content, created_at=message.created_at)
        for message in messages
    ]


@router.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
def send_session_message(
    session_id: SessionId,
    request: SendMessageRequest,
    db: DbSession,
    llm_service: LlmService,
) -> SendMessageResponse:
    try:
        assistant_message, state = persist_message_exchange(
            db,
            parse_session_id(session_id),
            request.message,
            llm_service=llm_service,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found") from exc
    except GeminiServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service is temporarily unavailable",
        ) from exc

    return SendMessageResponse(assistant_message=assistant_message, state=state)


@router.get("/sessions/{session_id}/document")
def read_session_document(session_id: SessionId, db: DbSession) -> FileResponse:
    try:
        parsed_session_id = parse_session_id(session_id)
        document_path = get_document(db, parsed_session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found") from exc

    return FileResponse(
        path=document_path,
        media_type=DOCX_MEDIA_TYPE,
        filename=f"personal_wishes_{parsed_session_id}.docx",
    )
