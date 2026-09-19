from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.init_db import init_db
from backend.models.database import Session, State
from backend.schemas.state import PersonalWishesState


def make_test_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, TestingSessionLocal


def test_database_tables_can_be_initialized(tmp_path):
    engine, _ = make_test_session(tmp_path)

    init_db(engine)

    table_names = set(inspect(engine).get_table_names())
    assert {"sessions", "messages", "state"}.issubset(table_names)


def test_session_and_initial_state_can_be_persisted_and_retrieved(tmp_path):
    engine, TestingSessionLocal = make_test_session(tmp_path)
    Base.metadata.create_all(bind=engine)
    initial_state = PersonalWishesState()

    with TestingSessionLocal() as db:
        session = Session()
        db.add(session)
        db.flush()
        db.add(
            State(
                session_id=session.id,
                state_json=initial_state.model_dump_json(),
                version=1,
            )
        )
        db.commit()
        session_id = session.id

    with TestingSessionLocal() as db:
        persisted_session = db.scalar(select(Session).where(Session.id == session_id))

        assert persisted_session is not None
        assert persisted_session.state is not None
        assert persisted_session.state.version == 1
        assert PersonalWishesState.model_validate_json(persisted_session.state.state_json) == initial_state
