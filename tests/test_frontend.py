from unittest.mock import MagicMock, patch

import pytest
import requests

from frontend.api_client import BackendAPIError, BackendClient, get_backend_url
from frontend.display import (
    EMPTY_STATE,
    format_bool,
    format_optional_text,
    render_draft_preview,
    render_state_sections,
)


def test_get_backend_url_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("BACKEND_URL", raising=False)
    assert get_backend_url() == "http://127.0.0.1:8000"


def test_get_backend_url_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BACKEND_URL", "http://localhost:9000/")
    assert get_backend_url() == "http://localhost:9000"


def test_create_session_posts_to_sessions():
    client = BackendClient(base_url="http://example.test")
    response = MagicMock()
    response.status_code = 201
    response.json.return_value = {"session_id": "42"}

    with patch("frontend.api_client.requests.request", return_value=response) as mock_request:
        session_id = client.create_session()

    assert session_id == "42"
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert args[0] == "POST"
    assert args[1] == "http://example.test/sessions"


def test_send_message_posts_to_messages_endpoint():
    client = BackendClient(base_url="http://example.test")
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "assistant_message": "Thanks.",
        "state": dict(EMPTY_STATE),
    }

    with patch("frontend.api_client.requests.request", return_value=response) as mock_request:
        payload = client.send_message("7", "Hello")

    assert payload["assistant_message"] == "Thanks."
    args, kwargs = mock_request.call_args
    assert args[0] == "POST"
    assert args[1] == "http://example.test/sessions/7/messages"
    assert kwargs["json"] == {"message": "Hello"}


def test_get_document_uses_document_endpoint():
    client = BackendClient(base_url="http://example.test")
    response = MagicMock()
    response.status_code = 200
    response.headers = {
        "content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }
    response.content = b"PK\x03\x04fake-docx"

    with patch("frontend.api_client.requests.request", return_value=response) as mock_request:
        content = client.get_document("3")

    assert content.startswith(b"PK")
    args, _kwargs = mock_request.call_args
    assert args[0] == "GET"
    assert args[1] == "http://example.test/sessions/3/document"


def test_connection_error_is_user_friendly():
    client = BackendClient(base_url="http://example.test")
    with patch(
        "frontend.api_client.requests.request",
        side_effect=requests.ConnectionError("boom"),
    ):
        with pytest.raises(BackendAPIError, match="Unable to reach the backend"):
            client.health()


def test_http_error_hides_internal_details():
    client = BackendClient(base_url="http://example.test")
    response = MagicMock()
    response.status_code = 500
    response.text = "Traceback (most recent call last): secret internals"

    with patch("frontend.api_client.requests.request", return_value=response):
        with pytest.raises(BackendAPIError, match="backend encountered an error") as exc_info:
            client.get_state("1")

    assert "Traceback" not in str(exc_info.value)
    assert "secret" not in str(exc_info.value)


def test_format_null_and_bool_values():
    assert format_optional_text(None) == "Not confirmed"
    assert format_optional_text("Rahul") == "Rahul"
    assert format_bool(True) == "Yes"
    assert format_bool(False) == "No"
    assert format_bool(None) == "Not confirmed"


def test_state_display_handles_empty_state():
    sections = dict(render_state_sections(EMPTY_STATE))
    personal = "\n".join(sections["PERSONAL INFORMATION"])
    children = "\n".join(sections["CHILDREN"])
    gifts = "\n".join(sections["SPECIFIC GIFTS"])

    assert "Full Name: Not confirmed" in personal
    assert "Has Children: Not confirmed" in children
    assert "None specified" in gifts
    assert "•" not in children


def test_state_display_children_variants():
    no_children = render_state_sections({**EMPTY_STATE, "has_children": False})
    with_names = render_state_sections(
        {**EMPTY_STATE, "has_children": True, "children": ["Aarav", "Riya"]}
    )
    without_names = render_state_sections({**EMPTY_STATE, "has_children": True, "children": []})

    no_text = "\n".join(dict(no_children)["CHILDREN"])
    names_text = "\n".join(dict(with_names)["CHILDREN"])
    missing_text = "\n".join(dict(without_names)["CHILDREN"])

    assert "Has Children: No" in no_text
    assert "Aarav" not in no_text
    assert "• Aarav" in names_text
    assert "• Riya" in names_text
    assert "Not provided" in missing_text


def test_draft_preview_matches_document_rules():
    preview = render_draft_preview(
        {
            **EMPTY_STATE,
            "full_name": "Rahul Sharma",
            "covers_worldwide_assets": True,
            "has_children": True,
            "children": [],
            "executor": {"name": "Amit", "relationship": None},
            "specific_gifts": [],
            "additional_wishes": None,
        }
    )

    assert "PERSONAL WISHES DOCUMENT" in preview
    assert "FICTIONAL DOCUMENT — NOT LEGAL ADVICE" in preview
    assert "Full Name: Rahul Sharma" in preview
    assert "Worldwide Assets: Yes" in preview
    assert "Children: Yes" in preview
    assert "Children's Names: Not provided" in preview
    assert "Executor Name: Amit" in preview
    assert "Relationship: Not confirmed" in preview
    assert "None specified" in preview


def test_frontend_app_module_imports():
    import frontend.app as app_module

    assert callable(app_module.main)
    assert "BackendClient" in app_module.__dict__ or hasattr(app_module, "BackendClient")


def test_session_id_persists_across_reruns():
    import frontend.app as app_module

    fake_state: dict = {}
    client = MagicMock()
    client.create_session.return_value = "99"

    first = app_module.ensure_backend_session_id(fake_state, client)
    second = app_module.ensure_backend_session_id(fake_state, client)

    assert first == "99"
    assert second == "99"
    assert fake_state["session_id"] == "99"
    client.create_session.assert_called_once()
