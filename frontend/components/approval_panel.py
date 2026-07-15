import os

import streamlit as st

from components.api_client import post_json


def render_approval_panel() -> None:
    """Render the human-in-the-loop approval panel."""
    st.warning("⚠️ The Data Engineer is requesting approval to update the Semantic Layer.")

    col1, col2 = st.columns(2)
    feedback = st.text_input("Feedback (optional)", key="approval_feedback")

    with col1:
        if st.button("✅ Approve", type="primary", use_container_width=True):
            _handle_approval(approved=True, feedback=feedback)

    with col2:
        if st.button("❌ Reject", use_container_width=True):
            _handle_approval(approved=False, feedback=feedback)


def _handle_approval(approved: bool, feedback: str) -> None:
    """Send approval/rejection to backend and update UI."""
    try:
        data = post_json(
            "/api/v1/approval/",
            {
                "thread_id": st.session_state.thread_id,
                "approved": approved,
                "feedback": feedback or None,
            },
        )

        status = "Approved" if approved else "Rejected"
        content = f"**[{data['agent']}] ({status})**\n\n{data['content']}"
        st.session_state.messages.append({"role": "assistant", "content": content})
        st.session_state.pending_approval = False
        st.rerun()

    except httpx.HTTPError as e:
        st.error(f"Failed to send approval: {e}")
