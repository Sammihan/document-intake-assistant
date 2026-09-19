from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.state import PersonalWishesState


class HealthResponse(BaseModel):
    status: str


class CreateSessionResponse(BaseModel):
    session_id: str


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    message: str = Field(min_length=1)


class MessageResponse(BaseModel):
    role: str
    content: str
    created_at: datetime


class SendMessageResponse(BaseModel):
    assistant_message: str
    state: PersonalWishesState
