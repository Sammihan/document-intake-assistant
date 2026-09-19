from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.main import create_app
from backend.api.routes.sessions import get_llm_service
from backend.database.base import Base
from backend.database.session import get_db
from backend.llm.gemini import GeminiServiceError
from backend.schemas.llm import ExtractedFields, LLMExtractionResponse


class MockLLMService:
    def __init__(self) -> None:
        self.calls = []
        self.responses = [
            LLMExtractionResponse(
                extracted_fields=ExtractedFields(),
                assistant_message="Thanks. What is your full name?",
                needs_clarification=True,
                clarification_reason="full_name is missing",
            )
        ]

    def extract(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.responses) > 1:
            response = self.responses.pop(0)
        else:
            response = self.responses[0]
        if isinstance(response, GeminiServiceError):
            raise response
        return response


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[OrmSession, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app(initialize_database=False)
    mock_llm = MockLLMService()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_service] = lambda: mock_llm

    with TestClient(app) as test_client:
        test_client.app.state.mock_llm = mock_llm
        test_client.app.state.TestingSessionLocal = TestingSessionLocal
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
