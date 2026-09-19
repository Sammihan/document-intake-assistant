from fastapi.testclient import TestClient

from backend.models.database import State
from backend.schemas.llm import ExtractedExecutor, ExtractedFields, LLMExtractionResponse
from tests.helpers import create_session


def queue(
    client: TestClient,
    extracted_fields: ExtractedFields,
    *,
    assistant_message: str = "Thanks.",
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


def queue_many(client: TestClient, responses: list[LLMExtractionResponse]) -> None:
    client.app.state.mock_llm.responses = responses


def send(client: TestClient, session_id: str, message: str):
    return client.post(f"/sessions/{session_id}/messages", json={"message": message})


def state(client: TestClient, session_id: str) -> dict:
    response = client.get(f"/sessions/{session_id}/state")
    assert response.status_code == 200
    return response.json()


def state_version(client: TestClient, session_id: str) -> int:
    with client.app.state.TestingSessionLocal() as db:
        persisted = db.get(State, int(session_id))
        assert persisted is not None
        return persisted.version


def test_new_address_extraction(client: TestClient):
    session_id = create_session(client)
    queue(client, ExtractedFields(home_address="25 FC Road, Pune"))

    response = send(client, session_id, "I live at 25 FC Road, Pune.")

    assert response.status_code == 200
    assert response.json()["state"]["home_address"] == "25 FC Road, Pune"


def test_missing_field_follow_up_moves_past_confirmed_name_when_message_empty(client: TestClient):
    session_id = create_session(client)
    queue(client, ExtractedFields(full_name="Rahul Sharma"), assistant_message="")

    response = send(client, session_id, "My name is Rahul Sharma.")

    message = response.json()["assistant_message"].lower()
    assert "address" in message
    assert "name" not in message


def test_valid_llm_assistant_message_is_preserved(client: TestClient):
    session_id = create_session(client)
    queue(
        client,
        ExtractedFields(full_name="Rahul Sharma"),
        assistant_message="Hello Rahul! Could you tell me your current residential address?",
    )

    response = send(client, session_id, "My name is Rahul Sharma.")

    assert response.status_code == 200
    assert response.json()["assistant_message"] == "Hello Rahul! Could you tell me your current residential address?"


def test_no_repeated_question_for_confirmed_fields(client: TestClient):
    session_id = create_session(client)
    queue_many(
        client,
        [
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(full_name="Rahul Sharma", home_address="Pune"),
                assistant_message="",
                needs_clarification=False,
                clarification_reason=None,
            ),
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(covers_worldwide_assets=True),
                assistant_message="",
                needs_clarification=False,
                clarification_reason=None,
            ),
        ],
    )

    send(client, session_id, "My name is Rahul Sharma and I live in Pune.")
    response = send(client, session_id, "Yes, cover worldwide assets.")

    message = response.json()["assistant_message"].lower()
    assert "children" in message
    assert "name" not in message
    assert "address" not in message


def test_executor_name_without_relationship_does_not_invent_relationship(client: TestClient):
    session_id = create_session(client)
    queue(client, ExtractedFields(executor=ExtractedExecutor(name="John")), assistant_message="")

    response = send(client, session_id, "John will be my executor.")

    executor = response.json()["state"]["executor"]
    assert executor["name"] == "John"
    assert executor["relationship"] is None
    assert "relationship" in response.json()["assistant_message"].lower()


def test_explicit_address_correction(client: TestClient):
    session_id = create_session(client)
    queue_many(
        client,
        [
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(home_address="12 MG Road"),
                assistant_message="Thanks.",
                needs_clarification=False,
                clarification_reason=None,
            ),
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(home_address="25 FC Road, Pune"),
                assistant_message="Updated.",
                needs_clarification=False,
                clarification_reason=None,
            ),
        ],
    )

    send(client, session_id, "I live at 12 MG Road.")
    response = send(client, session_id, "Correction: my address is 25 FC Road, Pune.")

    assert response.json()["state"]["home_address"] == "25 FC Road, Pune"


def test_direct_declarative_name_replacement(client: TestClient):
    session_id = create_session(client)
    queue_many(
        client,
        [
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(full_name="Sammian"),
                assistant_message="Recorded name as Sammian.",
                needs_clarification=False,
            ),
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(full_name="Sam"),
                assistant_message="Updated name to Sam.",
                needs_clarification=False,
            ),
        ],
    )

    send(client, session_id, "My name is Sammian")
    response = send(client, session_id, "My name is Sam")

    assert response.status_code == 200
    assert response.json()["state"]["full_name"] == "Sam"


def test_direct_declarative_address_replacement(client: TestClient):
    session_id = create_session(client)
    queue_many(
        client,
        [
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(home_address="12 MG Road"),
                assistant_message="Recorded address.",
                needs_clarification=False,
            ),
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(home_address="25 FC Road, Pune"),
                assistant_message="Updated address.",
                needs_clarification=False,
            ),
        ],
    )

    send(client, session_id, "I live at 12 MG Road")
    response = send(client, session_id, "My address is 25 FC Road, Pune")

    assert response.status_code == 200
    assert response.json()["state"]["home_address"] == "25 FC Road, Pune"


def test_direct_declarative_executor_replacement(client: TestClient):
    session_id = create_session(client)
    queue_many(
        client,
        [
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(executor=ExtractedExecutor(name="John")),
                assistant_message="Recorded John as executor.",
                needs_clarification=False,
            ),
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(executor=ExtractedExecutor(name="David")),
                assistant_message="Updated executor to David.",
                needs_clarification=False,
            ),
        ],
    )

    send(client, session_id, "John will be my executor")
    response = send(client, session_id, "My executor is David")

    assert response.status_code == 200
    assert response.json()["state"]["executor"]["name"] == "David"


def test_natural_corrections_update_state(client: TestClient):
    cases = [
        ("Please update my address to 25 FC Road, Pune.", ExtractedFields(home_address="25 FC Road, Pune"), "home_address", "25 FC Road, Pune"),
        ("Modify my name to Priya Sharma.", ExtractedFields(full_name="Priya Sharma"), "full_name", "Priya Sharma"),
        ("Revise my address to 90 Park Street.", ExtractedFields(home_address="90 Park Street"), "home_address", "90 Park Street"),
        ("My address is now 100 Main Road.", ExtractedFields(home_address="100 Main Road"), "home_address", "100 Main Road"),
        ("No my address is 200 Broad Street.", ExtractedFields(home_address="200 Broad Street"), "home_address", "200 Broad Street"),
    ]
    for msg, extracted, key, expected_val in cases:
        session_id = create_session(client)
        queue_many(
            client,
            [
                LLMExtractionResponse(
                    extracted_fields=ExtractedFields(full_name="Rahul Sharma", home_address="12 MG Road"),
                    assistant_message="Recorded.",
                    needs_clarification=False,
                ),
                LLMExtractionResponse(
                    extracted_fields=extracted,
                    assistant_message="Updated your information.",
                    needs_clarification=False,
                ),
            ],
        )
        send(client, session_id, "My name is Rahul Sharma and I live at 12 MG Road.")
        res = send(client, session_id, msg)
        assert res.status_code == 200
        assert res.json()["state"][key] == expected_val


def test_executor_relationship_correction(client: TestClient):
    session_id = create_session(client)
    queue_many(
        client,
        [
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(executor=ExtractedExecutor(relationship="brother")),
                assistant_message="Thanks.",
                needs_clarification=False,
                clarification_reason=None,
            ),
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(executor=ExtractedExecutor(relationship="sister")),
                assistant_message="Updated.",
                needs_clarification=False,
                clarification_reason=None,
            ),
        ],
    )

    send(client, session_id, "The executor is my brother.")
    response = send(client, session_id, "Actually, my sister will be the executor.")

    assert response.json()["state"]["executor"]["relationship"] == "sister"


def test_children_false_consistency_does_not_ask_for_child_names(client: TestClient):
    session_id = create_session(client)
    queue(client, ExtractedFields(has_children=False), assistant_message="")

    response = send(client, session_id, "I don't have any children.")

    body = response.json()
    assert body["state"]["has_children"] is False
    assert body["state"]["children"] == []
    assert "children's names" not in body["assistant_message"].lower()


def test_children_true_with_names(client: TestClient):
    session_id = create_session(client)
    queue(client, ExtractedFields(has_children=True, children=["Aarav", "Riya"]))

    response = send(client, session_id, "I have two children, Aarav and Riya.")

    assert response.json()["state"]["has_children"] is True
    assert response.json()["state"]["children"] == ["Aarav", "Riya"]


def test_correction_from_no_children_to_children(client: TestClient):
    session_id = create_session(client)
    queue_many(
        client,
        [
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(has_children=False),
                assistant_message="Thanks.",
                needs_clarification=False,
                clarification_reason=None,
            ),
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(has_children=True, children=["Aarav", "Riya"]),
                assistant_message="Updated.",
                needs_clarification=False,
                clarification_reason=None,
            ),
        ],
    )

    send(client, session_id, "I don't have children.")
    response = send(client, session_id, "Actually, I have two children, Aarav and Riya.")

    assert response.json()["state"]["has_children"] is True
    assert response.json()["state"]["children"] == ["Aarav", "Riya"]


def test_clear_child_statement_can_correct_prior_no_children(client: TestClient):
    session_id = create_session(client)
    queue_many(
        client,
        [
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(has_children=False),
                assistant_message="Thanks.",
                needs_clarification=False,
                clarification_reason=None,
            ),
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(has_children=True, children=["Aarav"]),
                assistant_message="Thanks, I updated that.",
                needs_clarification=False,
                clarification_reason=None,
            ),
        ],
    )

    send(client, session_id, "I have no children.")
    response = send(client, session_id, "I have a child named Aarav.")

    assert response.json()["state"]["has_children"] is True
    assert response.json()["state"]["children"] == ["Aarav"]


def test_child_count_beyond_three_and_daughter_corrections(client: TestClient):
    for phrase, count_names in [
        ("I have four children: A, B, C, D.", ["A", "B", "C", "D"]),
        ("I have 4 children: A, B, C, D.", ["A", "B", "C", "D"]),
        ("I have a daughter named Sarah.", ["Sarah"]),
    ]:
        session_id = create_session(client)
        queue_many(
            client,
            [
                LLMExtractionResponse(
                    extracted_fields=ExtractedFields(has_children=False),
                    assistant_message="Recorded.",
                    needs_clarification=False,
                ),
                LLMExtractionResponse(
                    extracted_fields=ExtractedFields(has_children=True, children=count_names),
                    assistant_message="Updated children.",
                    needs_clarification=False,
                ),
            ],
        )
        send(client, session_id, "I have no children.")
        res = send(client, session_id, phrase)
        assert res.status_code == 200
        assert res.json()["state"]["has_children"] is True
        assert res.json()["state"]["children"] == count_names


def test_ambiguous_child_information_does_not_overwrite_confirmed_no_children(client: TestClient):
    session_id = create_session(client)
    queue_many(
        client,
        [
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(has_children=False),
                assistant_message="Thanks.",
                needs_clarification=False,
                clarification_reason=None,
            ),
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(children=["Aarav"]),
                assistant_message="Can you clarify whether you want to update your earlier answer about children?",
                needs_clarification=True,
                clarification_reason="possible child information conflicts with no children",
            ),
        ],
    )

    send(client, session_id, "I have no children.")
    response = send(client, session_id, "My son Aarav should receive the watch.")

    assert response.json()["state"]["has_children"] is False
    assert response.json()["state"]["children"] == []
    assert "clarify" in response.json()["assistant_message"].lower()


def test_conflicting_update_without_correction_safely_leaves_state_unchanged(client: TestClient):
    session_id = create_session(client)
    queue_many(
        client,
        [
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(home_address="Pune"),
                assistant_message="Recorded address as Pune.",
                needs_clarification=False,
            ),
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(home_address="Mumbai"),
                assistant_message="Recorded Mumbai.",
                needs_clarification=False,
            ),
        ],
    )

    send(client, session_id, "I live in Pune.")
    response = send(client, session_id, "The letters go to Mumbai.")

    assert response.status_code == 200
    assert response.json()["state"]["home_address"] == "Pune"
    msg = response.json()["assistant_message"].lower()
    assert "conflict" in msg
    assert "clarify" in msg or "update" in msg


def test_no_invented_values(client: TestClient):
    session_id = create_session(client)
    queue(client, ExtractedFields(has_children=True), assistant_message="")

    response = send(client, session_id, "I have some children.")

    assert response.json()["state"]["has_children"] is True
    assert response.json()["state"]["children"] == []
    assert "children" in response.json()["assistant_message"].lower()


def test_state_version_increments_only_when_state_changes(client: TestClient):
    session_id = create_session(client)
    assert state_version(client, session_id) == 1
    queue_many(
        client,
        [
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(full_name="Rahul Sharma"),
                assistant_message="Thanks.",
                needs_clarification=False,
                clarification_reason=None,
            ),
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(),
                assistant_message="Could you clarify?",
                needs_clarification=True,
                clarification_reason="no extractable information",
            ),
        ],
    )

    send(client, session_id, "My name is Rahul Sharma.")
    assert state_version(client, session_id) == 2
    send(client, session_id, "Could you repeat that?")
    assert state_version(client, session_id) == 2
