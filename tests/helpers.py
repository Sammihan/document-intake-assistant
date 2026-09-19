from fastapi.testclient import TestClient


def create_session(client: TestClient) -> str:
    response = client.post("/sessions")
    assert response.status_code == 201
    return response.json()["session_id"]
