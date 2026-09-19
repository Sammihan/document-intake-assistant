import pytest
from pydantic import ValidationError

from backend.schemas.state import Executor, PersonalWishesState


def test_empty_personal_wishes_state_can_be_created():
    state = PersonalWishesState()

    assert state.full_name is None
    assert state.home_address is None
    assert state.covers_worldwide_assets is None
    assert state.has_children is None
    assert state.children == []
    assert state.executor == Executor()
    assert state.specific_gifts == []
    assert state.additional_wishes is None


def test_valid_populated_personal_wishes_state_validates():
    state = PersonalWishesState(
        full_name="Sam Example",
        home_address="10 Test Street",
        covers_worldwide_assets=True,
        has_children=True,
        children=["Avery Example", "Riley Example"],
        executor=Executor(name="Jordan Example", relationship="Sibling"),
        specific_gifts=["Watch to Avery", "Books to Riley"],
        additional_wishes="Prefer a simple ceremony.",
    )

    assert state.full_name == "Sam Example"
    assert state.executor.relationship == "Sibling"
    assert state.children == ["Avery Example", "Riley Example"]


def test_invalid_field_types_are_rejected():
    with pytest.raises(ValidationError):
        PersonalWishesState(full_name=123)

    with pytest.raises(ValidationError):
        PersonalWishesState(covers_worldwide_assets="yes")

    with pytest.raises(ValidationError):
        PersonalWishesState(children=["Avery", 42])


def test_children_must_be_empty_when_has_children_is_false():
    with pytest.raises(ValidationError):
        PersonalWishesState(has_children=False, children=["Avery Example"])
