"""HTTP client for the Document Intake Assistant FastAPI backend."""

from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


class BackendAPIError(Exception):
    """User-facing error for backend HTTP failures."""


def get_backend_url() -> str:
    return os.getenv("BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/")


class BackendClient:
    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = (base_url or get_backend_url()).rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        try:
            response = requests.request(
                method,
                self._url(path),
                timeout=self.timeout,
                **kwargs,
            )
        except requests.Timeout as exc:
            raise BackendAPIError(
                "The backend did not respond in time. Please try again."
            ) from exc
        except requests.ConnectionError as exc:
            raise BackendAPIError(
                "Unable to reach the backend. Make sure the FastAPI server is running."
            ) from exc
        except requests.RequestException as exc:
            raise BackendAPIError(
                "A network error occurred while contacting the backend."
            ) from exc

        if response.status_code >= 400:
            raise BackendAPIError(self._friendly_http_error(response))
        return response

    @staticmethod
    def _friendly_http_error(response: requests.Response) -> str:
        if response.status_code == 404:
            return "Session not found. Please refresh the page to start a new session."
        if response.status_code == 503:
            return "The assistant service is temporarily unavailable. Please try again shortly."
        if response.status_code >= 500:
            return "The backend encountered an error. Please try again."
        return "The backend rejected the request. Please try again."

    def health(self) -> dict[str, Any]:
        response = self._request("GET", "/health")
        try:
            return response.json()
        except ValueError as exc:
            raise BackendAPIError(
                "Received an unexpected response from the backend."
            ) from exc

    def create_session(self) -> str:
        response = self._request("POST", "/sessions")
        try:
            payload = response.json()
            session_id = payload["session_id"]
        except (ValueError, KeyError, TypeError) as exc:
            raise BackendAPIError(
                "Received an unexpected response while creating a session."
            ) from exc
        if not isinstance(session_id, str) or not session_id:
            raise BackendAPIError("Received an invalid session id from the backend.")
        return session_id

    def get_state(self, session_id: str) -> dict[str, Any]:
        response = self._request("GET", f"/sessions/{session_id}/state")
        try:
            return response.json()
        except ValueError as exc:
            raise BackendAPIError(
                "Received an unexpected state response from the backend."
            ) from exc

    def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        response = self._request("GET", f"/sessions/{session_id}/messages")
        try:
            payload = response.json()
        except ValueError as exc:
            raise BackendAPIError(
                "Received an unexpected messages response from the backend."
            ) from exc
        if not isinstance(payload, list):
            raise BackendAPIError(
                "Received an unexpected messages response from the backend."
            )
        return payload

    def send_message(self, session_id: str, message: str) -> dict[str, Any]:
        response = self._request(
            "POST",
            f"/sessions/{session_id}/messages",
            json={"message": message},
        )
        try:
            payload = response.json()
            if "assistant_message" not in payload or "state" not in payload:
                raise KeyError("assistant_message/state")
            return payload
        except (ValueError, KeyError, TypeError) as exc:
            raise BackendAPIError(
                "Received an unexpected response after sending a message."
            ) from exc

    def get_document(self, session_id: str) -> bytes:
        response = self._request("GET", f"/sessions/{session_id}/document")
        content_type = response.headers.get("content-type", "")
        if DOCX_MEDIA_TYPE not in content_type and response.content[:2] != b"PK":
            raise BackendAPIError("The backend did not return a valid document file.")
        return response.content
