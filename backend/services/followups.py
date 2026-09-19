from dataclasses import dataclass

from backend.schemas.state import PersonalWishesState


CHILD_NAME_DECLINE_MARKERS = (
    "don't want to provide",
    "do not want to provide",
    "prefer not to provide",
    "rather not provide",
)


@dataclass(frozen=True)
class MissingField:
    name: str
    question: str


def get_next_missing_field(state: PersonalWishesState, *, latest_user_message: str = "") -> MissingField | None:
    if state.has_children is True and not state.children and not _declines_child_names(latest_user_message):
        return MissingField("children", "What are your children's names?")
    if state.executor.name is not None and state.executor.relationship is None:
        return MissingField(
            "executor.relationship",
            "What is your executor's relationship to you?",
        )
    if state.executor.relationship is not None and state.executor.name is None:
        return MissingField("executor.name", "Who should be your executor?")
    if state.full_name is None:
        return MissingField("full_name", "What is your full name?")
    if state.home_address is None:
        return MissingField("home_address", "What is your home address?")
    if state.covers_worldwide_assets is None:
        return MissingField(
            "covers_worldwide_assets",
            "Should this fictional document cover assets worldwide?",
        )
    if state.has_children is None:
        return MissingField("has_children", "Do you have any children?")
    if state.executor.name is None:
        return MissingField("executor.name", "Who should be your executor?")
    if state.executor.relationship is None:
        return MissingField(
            "executor.relationship",
            "What is your executor's relationship to you?",
        )
    if not state.specific_gifts:
        return MissingField(
            "specific_gifts",
            "Are there any specific gifts you want to include?",
        )
    if state.additional_wishes is None:
        return MissingField(
            "additional_wishes",
            "Do you have any additional wishes to include?",
        )
    return None


def compose_assistant_message(
    *,
    llm_message: str,
    updated_state: PersonalWishesState,
    needs_clarification: bool,
    latest_user_message: str,
) -> str:
    if llm_message and llm_message.strip():
        return llm_message

    next_missing = get_next_missing_field(updated_state, latest_user_message=latest_user_message)
    if next_missing is None:
        return "Thanks, I've recorded that."
    return f"Thanks, I've recorded that. {next_missing.question}"



def _declines_child_names(user_message: str) -> bool:
    normalized = user_message.lower()
    return any(marker in normalized for marker in CHILD_NAME_DECLINE_MARKERS)
