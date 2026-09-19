import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.llm.gemini import GeminiServiceError
from backend.schemas.llm import ExtractedExecutor, ExtractedFields, LLMExtractionResponse
from tests.helpers import create_session


def queue_response(
    client: TestClient,
    *,
    extracted_fields: ExtractedFields,
    assistant_message: str = "Thanks. What should we capture next?",
    needs_clarification: bool = False,
    clarification_reason: str | None = None,
) -> None:
    client.app.state.mock_llm.responses = [
        LLMExtractionResponse(
            extracted_fields=extracted_fields,
            assistant_message=assistant_message,
            needs_clarification=needs_clarification,
            clarification_reason=clarification_reason,
        )
    ]


def post_message(client: TestClient, session_id: str, message: str):
    return client.post(f"/sessions/{session_id}/messages", json={"message": message})


def get_state(client: TestClient, session_id: str) -> dict:
    return client.get(f"/sessions/{session_id}/state").json()


def test_user_message_with_name_updates_full_name(client: TestClient):
    session_id = create_session(client)
    queue_response(
        client,
        extracted_fields=ExtractedFields(full_name="Rahul Sharma"),
        assistant_message="Thanks, Rahul. What is your home address?",
    )

    response = post_message(client, session_id, "My name is Rahul Sharma.")

    assert response.status_code == 200
    assert response.json()["state"]["full_name"] == "Rahul Sharma"
    assert get_state(client, session_id)["full_name"] == "Rahul Sharma"


def test_multiple_fields_in_one_message_update_state(client: TestClient):
    session_id = create_session(client)
    queue_response(
        client,
        extracted_fields=ExtractedFields(
            full_name="Rahul Sharma",
            home_address="Pune",
            has_children=True,
            children=["Alice", "Ben"],
        ),
        assistant_message="Thanks. Who should be your executor?",
    )

    response = post_message(client, session_id, "My name is Rahul Sharma, I live in Pune, and I have two children Alice and Ben.")

    state = response.json()["state"]
    assert state["full_name"] == "Rahul Sharma"
    assert state["home_address"] == "Pune"
    assert state["has_children"] is True
    assert state["children"] == ["Alice", "Ben"]


def test_missing_information_does_not_get_invented(client: TestClient):
    session_id = create_session(client)
    queue_response(
        client,
        extracted_fields=ExtractedFields(full_name="Rahul Sharma"),
        assistant_message="Thanks, Rahul. What is your home address?",
    )

    response = post_message(client, session_id, "My name is Rahul Sharma.")

    state = response.json()["state"]
    assert state["home_address"] is None
    assert state["executor"] == {"name": None, "relationship": None}
    assert state["children"] == []


def test_ambiguous_executor_captures_relationship_and_keeps_name_unknown(client: TestClient):
    session_id = create_session(client)
    queue_response(
        client,
        extracted_fields=ExtractedFields(executor=ExtractedExecutor(relationship="brother")),
        assistant_message="What is your brother's name?",
        needs_clarification=True,
        clarification_reason="executor name is missing",
    )

    response = post_message(client, session_id, "My brother will be executor.")

    assert response.status_code == 200
    assert response.json()["assistant_message"] == "What is your brother's name?"
    assert response.json()["state"]["executor"] == {"name": None, "relationship": "brother"}


def test_explicit_correction_replaces_confirmed_value(client: TestClient):
    session_id = create_session(client)
    client.app.state.mock_llm.responses = [
        LLMExtractionResponse(
            extracted_fields=ExtractedFields(full_name="Rahul Sharma"),
            assistant_message="Thanks, Rahul.",
            needs_clarification=False,
            clarification_reason=None,
        ),
        LLMExtractionResponse(
            extracted_fields=ExtractedFields(full_name="John Sharma"),
            assistant_message="Got it, I updated your name.",
            needs_clarification=False,
            clarification_reason=None,
        ),
    ]

    first = post_message(client, session_id, "My name is Rahul Sharma.")
    second = post_message(client, session_id, "Actually, my name is John Sharma.")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["state"]["full_name"] == "John Sharma"
    assert get_state(client, session_id)["full_name"] == "John Sharma"


def test_contradictory_information_does_not_overwrite_confirmed_state(client: TestClient):
    session_id = create_session(client)
    client.app.state.mock_llm.responses = [
        LLMExtractionResponse(
            extracted_fields=ExtractedFields(has_children=False),
            assistant_message="Thanks, I have recorded that you have no children.",
            needs_clarification=False,
            clarification_reason=None,
        ),
        LLMExtractionResponse(
            extracted_fields=ExtractedFields(has_children=True, children=["Alice"]),
            assistant_message="I need to clarify: you previously said you have no children. Should I update that?",
            needs_clarification=True,
            clarification_reason="child information conflicts with confirmed no children state",
        ),
    ]

    first = post_message(client, session_id, "I do not have children.")
    second = post_message(client, session_id, "My daughter Alice should receive my books.")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["state"]["has_children"] is False
    assert second.json()["state"]["children"] == []
    assert get_state(client, session_id)["children"] == []


def test_invalid_malformed_gemini_output_is_rejected_by_schema():
    with pytest.raises(ValidationError):
        LLMExtractionResponse.model_validate(
            {
                "extracted_fields": {"full_name": 123},
                "assistant_message": "",
                "needs_clarification": "no",
                "clarification_reason": None,
            }
        )


def test_gemini_api_failure_does_not_corrupt_existing_state(client: TestClient):
    session_id = create_session(client)
    queue_response(
        client,
        extracted_fields=ExtractedFields(full_name="Rahul Sharma"),
        assistant_message="Thanks, Rahul.",
    )
    first = post_message(client, session_id, "My name is Rahul Sharma.")
    assert first.status_code == 200

    client.app.state.mock_llm.responses = [GeminiServiceError("provider unavailable")]
    failed = post_message(client, session_id, "Actually, my name is John Sharma.")

    assert failed.status_code == 503
    assert get_state(client, session_id)["full_name"] == "Rahul Sharma"


def test_confirmed_information_is_supplied_to_llm_context(client: TestClient):
    session_id = create_session(client)
    client.app.state.mock_llm.responses = [
        LLMExtractionResponse(
            extracted_fields=ExtractedFields(full_name="Rahul Sharma"),
            assistant_message="Thanks, Rahul.",
            needs_clarification=False,
            clarification_reason=None,
        ),
        LLMExtractionResponse(
            extracted_fields=ExtractedFields(home_address="Pune"),
            assistant_message="Thanks. I have your address too.",
            needs_clarification=False,
            clarification_reason=None,
        ),
    ]

    post_message(client, session_id, "My name is Rahul Sharma.")
    post_message(client, session_id, "I live in Pune.")

    second_call_state = client.app.state.mock_llm.calls[1]["current_state"]
    assert second_call_state.full_name == "Rahul Sharma"


def test_conflict_safely_preserves_state_and_prompts_clarification(client: TestClient):
    session_id = create_session(client)
    client.app.state.mock_llm.responses = [
        LLMExtractionResponse(
            extracted_fields=ExtractedFields(full_name="Rahul Sharma"),
            assistant_message="Thanks Rahul.",
            needs_clarification=False,
        ),
        LLMExtractionResponse(
            extracted_fields=ExtractedFields(full_name="Amit Patel"),
            assistant_message="Got it, Amit.",
            needs_clarification=False,
        ),
    ]

    first = post_message(client, session_id, "My name is Rahul Sharma.")
    assert first.status_code == 200
    assert first.json()["state"]["full_name"] == "Rahul Sharma"

    second = post_message(client, session_id, "Hello from Amit Patel.")
    assert second.status_code == 200
    assert second.json()["state"]["full_name"] == "Rahul Sharma"
    assert "conflict" in second.json()["assistant_message"].lower()
    assert "clarify" in second.json()["assistant_message"].lower() or "update" in second.json()["assistant_message"].lower()


def test_empty_llm_message_falls_back_to_deterministic_followup(client: TestClient):
    session_id = create_session(client)
    queue_response(
        client,
        extracted_fields=ExtractedFields(full_name="Rahul Sharma"),
        assistant_message="",
    )

    response = post_message(client, session_id, "My name is Rahul Sharma.")
    assert response.status_code == 200
    assert "home address" in response.json()["assistant_message"].lower()
