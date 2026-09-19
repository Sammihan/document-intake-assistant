"""Display helpers for structured state and draft-document preview.

Formatting mirrors backend/services/document_generator.py so the UI preview
reflects the same information used to generate the downloadable .docx.
State JSON from the API remains the only data source.
"""

from __future__ import annotations

from typing import Any

NOT_CONFIRMED = "Not confirmed"
NONE_SPECIFIED = "None specified"
NOT_PROVIDED = "Not provided"


def format_optional_text(value: str | None) -> str:
    if value is None:
        return NOT_CONFIRMED
    return value


def format_bool(value: bool | None) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return NOT_CONFIRMED


def _confirmed_marker(is_confirmed: bool) -> str:
    return "✓" if is_confirmed else "○"


def render_state_sections(state: dict[str, Any]) -> list[tuple[str, list[str]]]:
    """Return human-readable sections for the Current Information panel."""
    executor = state.get("executor") or {}
    children = state.get("children") or []
    specific_gifts = state.get("specific_gifts") or []
    has_children = state.get("has_children")

    personal = [
        f"{_confirmed_marker(state.get('full_name') is not None)} Full Name: {format_optional_text(state.get('full_name'))}",
        f"{_confirmed_marker(state.get('home_address') is not None)} Home Address: {format_optional_text(state.get('home_address'))}",
    ]

    assets = [
        f"{_confirmed_marker(state.get('covers_worldwide_assets') is not None)} Worldwide Assets: {format_bool(state.get('covers_worldwide_assets'))}",
    ]

    children_lines = [
        f"{_confirmed_marker(has_children is not None)} Has Children: {format_bool(has_children)}",
    ]
    if has_children is True:
        if children:
            children_lines.extend(f"• {name}" for name in children)
        else:
            children_lines.append(f"• Children's Names: {NOT_PROVIDED}")

    executor_lines = [
        f"{_confirmed_marker(executor.get('name') is not None)} Name: {format_optional_text(executor.get('name'))}",
        f"{_confirmed_marker(executor.get('relationship') is not None)} Relationship: {format_optional_text(executor.get('relationship'))}",
    ]

    if specific_gifts:
        gifts_lines = [f"• {gift}" for gift in specific_gifts]
    else:
        gifts_lines = [f"○ {NONE_SPECIFIED}"]

    additional = state.get("additional_wishes")
    wishes_lines = [
        f"{_confirmed_marker(additional is not None)} {format_optional_text(additional)}",
    ]

    return [
        ("PERSONAL INFORMATION", personal),
        ("ASSET COVERAGE", assets),
        ("CHILDREN", children_lines),
        ("EXECUTOR", executor_lines),
        ("SPECIFIC GIFTS", gifts_lines),
        ("ADDITIONAL WISHES", wishes_lines),
    ]


def render_draft_preview(state: dict[str, Any]) -> str:
    """Text preview matching the document generator's content rules."""
    executor = state.get("executor") or {}
    children = state.get("children") or []
    specific_gifts = state.get("specific_gifts") or []
    has_children = state.get("has_children")

    lines = [
        "PERSONAL WISHES DOCUMENT",
        "",
        "FICTIONAL DOCUMENT — NOT LEGAL ADVICE",
        "",
        "Personal Information",
        f"- Full Name: {format_optional_text(state.get('full_name'))}",
        f"- Home Address: {format_optional_text(state.get('home_address'))}",
        "",
        "Asset Coverage",
        f"- Worldwide Assets: {format_bool(state.get('covers_worldwide_assets'))}",
        "",
        "Children",
        f"- Children: {format_bool(has_children)}",
    ]

    if has_children is True:
        if children:
            lines.append(f"- Children's Names: {', '.join(children)}")
        else:
            lines.append(f"- Children's Names: {NOT_PROVIDED}")

    lines.extend(
        [
            "",
            "Executor",
            f"- Executor Name: {format_optional_text(executor.get('name'))}",
            f"- Relationship: {format_optional_text(executor.get('relationship'))}",
            "",
            "Specific Gifts",
        ]
    )

    if specific_gifts:
        lines.extend(f"- {gift}" for gift in specific_gifts)
    else:
        lines.append(f"- {NONE_SPECIFIED}")

    lines.extend(
        [
            "",
            "Additional Wishes",
            f"- {format_optional_text(state.get('additional_wishes'))}",
        ]
    )

    return "\n".join(lines)


EMPTY_STATE: dict[str, Any] = {
    "full_name": None,
    "home_address": None,
    "covers_worldwide_assets": None,
    "has_children": None,
    "children": [],
    "executor": {"name": None, "relationship": None},
    "specific_gifts": [],
    "additional_wishes": None,
}
