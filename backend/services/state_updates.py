import re
from copy import deepcopy
from typing import Any

from backend.schemas.llm import ExtractedFields
from backend.schemas.state import Executor, PersonalWishesState


CORRECTION_MARKERS = (
    "actually",
    "correction",
    "correct that",
    "correct my",
    "correct",
    "change that",
    "change my",
    "change",
    "update",
    "modify",
    "revise",
    "revision",
    "fix",
    "replace",
    "instead",
    "i meant",
    "rather",
    "not ",
    "no,",
    "no it's",
    "no, it's",
    "no it is",
    "no my",
    "that's wrong",
    "that is wrong",
    "mistake",
)

EXPLICIT_CORRECTION_PATTERNS = (
    re.compile(
        r"\b(?:actually|correction|correct(?:ed|ion|ing)?|change(?:d|s|ing)?|update(?:d|s|ing)?|modify|modified|modifying|revise(?:d|s|ing)?|revision|fix(?:ed|es|ing)?|replace(?:d|s|ing)?|instead|i\s+meant|rather|mistake|that'?s\s+wrong|that\s+is\s+wrong)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:no\s+my\b|no\s+it'?s\b|no\s+it\s+is\b|no,)", re.IGNORECASE),
    re.compile(
        r"\b(?:my\s+\w+\s+is\s+now\b|is\s+now\b|now\s+is\b|set\s+(?:my|the)\b|make\s+(?:my|the)\b|switch\s+(?:to|my)\b)",
        re.IGNORECASE,
    ),
)

CHILDREN_CORRECTION_PATTERN = re.compile(
    r"\bi\s+have\s+(?:(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|a|an|\w+)\s+)?(?:children|child|kids|son|sons|daughter|daughters)\b",
    re.IGNORECASE,
)

NO_CHILDREN_CORRECTION_PATTERN = re.compile(
    r"\b(?:i\s+have\s+no\s+children|i\s+do\s*n'?t\s+have\s+(?:any\s+)?children|no\s+children|do\s+not\s+have\s+(?:any\s+)?children)\b",
    re.IGNORECASE,
)


FIELD_DECLARATION_PATTERNS: dict[str, tuple[re.Pattern, ...]] = {
    "full_name": (
        re.compile(r"\b(?:my\s+(?:full\s+|legal\s+)?name\s+is|i\s+am|i'm|call\s+me)\b", re.IGNORECASE),
    ),
    "home_address": (
        re.compile(
            r"\b(?:my\s+(?:home\s+|current\s+|residential\s+)?address\s+is|my\s+residence\s+is|i\s+live\s+(?:at|in)|i\s+reside\s+(?:at|in))\b",
            re.IGNORECASE,
        ),
    ),
    "covers_worldwide_assets": (
        re.compile(r"\b(?:cover\s+(?:worldwide\s+assets|assets\s+worldwide)|worldwide\s+assets|assets\s+worldwide)\b", re.IGNORECASE),
    ),
    "additional_wishes": (
        re.compile(r"\b(?:my\s+(?:additional\s+)?wishes\s+(?:are|is)|additional\s+wishes\b)", re.IGNORECASE),
    ),
    "executor.name": (
        re.compile(
            r"\b(?:(?:my|the)\s+executor\s+(?:is|will\s+be|shall\s+be)|executor\s+(?:is|will\s+be))\b",
            re.IGNORECASE,
        ),
    ),
    "executor.relationship": (
        re.compile(r"\b(?:(?:my\s+|the\s+)?executor(?:'s)?\s+(?:relationship\s+is|is\s+my|will\s+be\s+my))\b", re.IGNORECASE),
        re.compile(
            r"\b(?:my\s+executor\s+(?:is|will\s+be)\s+(?:my\s+)?(?:brother|sister|friend|lawyer|spouse|wife|husband|son|daughter|mother|father|partner|cousin|sibling|niece|nephew))\b",
            re.IGNORECASE,
        ),
    ),
}


class StateUpdateConflictError(Exception):
    pass


def apply_extracted_fields(
    current_state: PersonalWishesState,
    extracted_fields: ExtractedFields,
    *,
    user_message: str,
) -> PersonalWishesState:
    updates = extracted_fields.model_dump(exclude_none=True)
    if not updates:
        return current_state

    is_correction = _is_explicit_correction(user_message)
    is_children_correction = is_correction or _is_children_correction(user_message, current_state, extracted_fields)
    next_data = current_state.model_dump(mode="python")
    _apply_scalar_updates(next_data, updates, current_state, is_correction, is_children_correction, user_message=user_message)
    _apply_executor_updates(next_data, updates, current_state, is_correction, user_message=user_message)

    if _has_children_conflict(current_state, extracted_fields, is_children_correction):
        raise StateUpdateConflictError("Extracted child information conflicts with the confirmed state")

    _apply_list_updates(next_data, updates, current_state, is_correction or is_children_correction)

    if updates.get("has_children") is False:
        next_data["children"] = []

    return PersonalWishesState.model_validate(next_data)


def _is_explicit_correction(user_message: str) -> bool:
    normalized = user_message.lower()
    if any(marker in normalized for marker in CORRECTION_MARKERS):
        return True
    return any(pattern.search(user_message) for pattern in EXPLICIT_CORRECTION_PATTERNS)


def _is_field_declaration(field_key: str, user_message: str) -> bool:
    patterns = FIELD_DECLARATION_PATTERNS.get(field_key, ())
    return any(pattern.search(user_message) for pattern in patterns)


def _is_children_correction(
    user_message: str,
    current_state: PersonalWishesState,
    extracted_fields: ExtractedFields,
) -> bool:
    if current_state.has_children is False:
        if extracted_fields.has_children is not True and not extracted_fields.children:
            return False
        return bool(CHILDREN_CORRECTION_PATTERN.search(user_message))
    if current_state.has_children is True:
        if extracted_fields.has_children is False:
            return bool(NO_CHILDREN_CORRECTION_PATTERN.search(user_message))
    return False


def _apply_scalar_updates(
    next_data: dict[str, Any],
    updates: dict[str, Any],
    current_state: PersonalWishesState,
    is_correction: bool,
    is_children_correction: bool,
    *,
    user_message: str = "",
) -> None:
    for field_name in (
        "full_name",
        "home_address",
        "covers_worldwide_assets",
        "has_children",
        "additional_wishes",
    ):
        if field_name not in updates:
            continue
        can_correct = (
            is_correction
            or (field_name == "has_children" and is_children_correction)
            or _is_field_declaration(field_name, user_message)
        )
        _set_confirmed_value(next_data, field_name, getattr(current_state, field_name), updates[field_name], can_correct)


def _apply_executor_updates(
    next_data: dict[str, Any],
    updates: dict[str, Any],
    current_state: PersonalWishesState,
    is_correction: bool,
    *,
    user_message: str = "",
) -> None:
    executor_updates = updates.get("executor")
    if not executor_updates:
        return

    executor_data = deepcopy(next_data["executor"])
    current_executor = current_state.executor or Executor()
    for field_name, new_value in executor_updates.items():
        can_correct = (
            is_correction
            or _is_field_declaration(f"executor.{field_name}", user_message)
            or _is_field_declaration("executor.name", user_message)
        )
        _set_confirmed_value(
            executor_data,
            field_name,
            getattr(current_executor, field_name),
            new_value,
            can_correct,
        )
    next_data["executor"] = executor_data


def _apply_list_updates(
    next_data: dict[str, Any],
    updates: dict[str, Any],
    current_state: PersonalWishesState,
    is_correction: bool,
) -> None:
    for field_name in ("children", "specific_gifts"):
        if field_name not in updates:
            continue
        current_value = getattr(current_state, field_name)
        new_value = updates[field_name]
        if not current_value or is_correction:
            next_data[field_name] = new_value
            continue
        next_data[field_name] = _merge_unique(current_value, new_value)


def _set_confirmed_value(
    data: dict[str, Any],
    field_name: str,
    current_value: Any,
    new_value: Any,
    is_correction: bool,
) -> None:
    if current_value is None or current_value == new_value or is_correction:
        data[field_name] = new_value
        return
    raise StateUpdateConflictError(f"{field_name} conflicts with the confirmed state")


def _merge_unique(current_items: list[str], new_items: list[str]) -> list[str]:
    merged = list(current_items)
    for item in new_items:
        if item not in merged:
            merged.append(item)
    return merged


def _has_children_conflict(
    current_state: PersonalWishesState,
    extracted_fields: ExtractedFields,
    is_correction: bool,
) -> bool:
    if is_correction:
        return False
    if current_state.has_children is False and extracted_fields.children:
        return True
    if current_state.has_children is False and extracted_fields.has_children is True:
        return True
    if current_state.has_children is True and extracted_fields.has_children is False:
        return True
    return False
