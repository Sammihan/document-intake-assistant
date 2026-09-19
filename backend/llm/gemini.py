import json
from typing import Protocol

from google import genai
from google.genai import types
from pydantic import ValidationError

from backend.config import GEMINI_API_KEY, GEMINI_MODEL
from backend.llm.prompts import PERSONAL_WISHES_SYSTEM_PROMPT
from backend.models.database import Message
from backend.schemas.llm import LLMExtractionResponse
from backend.schemas.state import PersonalWishesState


class GeminiServiceError(Exception):
    pass


class MissingGeminiConfigurationError(GeminiServiceError):
    pass


class LLMService(Protocol):
    def extract(
        self,
        *,
        current_state: PersonalWishesState,
        messages: list[Message],
        user_message: str,
    ) -> LLMExtractionResponse:
        pass


class GeminiClient:
    def __init__(self, api_key: str | None = GEMINI_API_KEY, model: str = GEMINI_MODEL) -> None:
        if not api_key:
            raise MissingGeminiConfigurationError("Gemini API key is not configured")
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def extract(
        self,
        *,
        current_state: PersonalWishesState,
        messages: list[Message],
        user_message: str,
    ) -> LLMExtractionResponse:
        prompt = build_extraction_prompt(current_state=current_state, messages=messages, user_message=user_message)
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=PERSONAL_WISHES_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                ),
            )
        except Exception as exc:
            raise GeminiServiceError("Gemini request failed") from exc

        response_text = getattr(response, "text", None)
        if not response_text:
            raise GeminiServiceError("Gemini returned an empty response")

        try:
            payload = json.loads(response_text)
            return LLMExtractionResponse.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise GeminiServiceError("Gemini returned malformed structured output") from exc


def build_extraction_prompt(
    *,
    current_state: PersonalWishesState,
    messages: list[Message],
    user_message: str,
) -> str:
    recent_messages = [
        {"role": message.role, "content": message.content}
        for message in messages[-10:]
    ]
    context = {
        "current_state": current_state.model_dump(mode="json"),
        "recent_conversation": recent_messages,
        "latest_user_message": user_message,
    }
    return json.dumps(context, ensure_ascii=False)
