"""Streamlit UI for the Document Intake Assistant.

Communicates with the FastAPI backend over HTTP only.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, MutableMapping

# Allow `streamlit run frontend/app.py` to import the frontend package.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from frontend.api_client import BackendAPIError, BackendClient
from frontend.display import EMPTY_STATE, render_draft_preview, render_state_sections


def ensure_backend_session_id(
    session_state: MutableMapping[str, Any],
    client: BackendClient,
) -> str:
    """Reuse an existing backend session_id; create one only when missing."""
    existing = session_state.get("session_id")
    if existing:
        return str(existing)

    session_id = client.create_session()
    session_state["session_id"] = session_id
    return session_id


def _ensure_session(client: BackendClient) -> bool:
    """Create a backend session once and persist its id in st.session_state."""
    try:
        session_id = ensure_backend_session_id(st.session_state, client)
        if "state" not in st.session_state or "messages" not in st.session_state:
            st.session_state.state = client.get_state(session_id)
            st.session_state.messages = client.get_messages(session_id)
        st.session_state.init_error = None
        return True
    except BackendAPIError as exc:
        st.session_state.init_error = str(exc)
        return False


def _refresh_from_backend(client: BackendClient) -> None:
    session_id = st.session_state.session_id
    st.session_state.state = client.get_state(session_id)
    st.session_state.messages = client.get_messages(session_id)


def _render_state_panel(state: dict) -> None:
    st.subheader("Current Information")
    for title, lines in render_state_sections(state):
        st.markdown(f"**{title}**")
        for line in lines:
            st.markdown(line)
        st.write("")


def _render_draft_panel(client: BackendClient, session_id: str, state: dict) -> None:
    st.subheader("Draft Document")
    st.caption("FICTIONAL DOCUMENT — NOT LEGAL ADVICE")
    st.text(render_draft_preview(state))

    st.write("")
    try:
        document_bytes = client.get_document(session_id)
        st.download_button(
            label="Download Draft Document",
            data=document_bytes,
            file_name=f"personal_wishes_{session_id}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    except BackendAPIError as exc:
        st.error(str(exc))


def _render_conversation(client: BackendClient, session_id: str) -> None:
    st.subheader("Conversation")
    st.caption("Corrections can be made naturally in chat (for example: “Actually, my name is Rohan.”).")

    messages = st.session_state.get("messages") or []
    for message in messages:
        role = message.get("role", "assistant")
        content = message.get("content", "")
        with st.chat_message(role if role in {"user", "assistant"} else "assistant"):
            st.markdown(content)

    prompt = st.chat_input("Type your message…")
    if prompt:
        try:
            result = client.send_message(session_id, prompt)
            st.session_state.state = result["state"]
            _refresh_from_backend(client)
            st.rerun()
        except BackendAPIError as exc:
            st.error(str(exc))


def main() -> None:
    st.set_page_config(page_title="Document Intake Assistant", layout="wide")
    st.title("Document Intake Assistant")
    st.markdown("Create a fictional Personal Wishes Document through conversation.")
    st.info("FICTIONAL DOCUMENT — NOT LEGAL ADVICE")

    client = BackendClient()

    if not _ensure_session(client):
        st.error(st.session_state.get("init_error") or "Unable to start a session.")
        st.stop()

    session_id = st.session_state.session_id

    if "state" not in st.session_state:
        st.session_state.state = dict(EMPTY_STATE)
    if "messages" not in st.session_state:
        st.session_state.messages = []

    try:
        _refresh_from_backend(client)
    except BackendAPIError as exc:
        st.warning(str(exc))

    left, right = st.columns(2)

    with left:
        _render_conversation(client, session_id)

    with right:
        _render_state_panel(st.session_state.state)
        st.divider()
        _render_draft_panel(client, session_id, st.session_state.state)


if __name__ == "__main__":
    main()
