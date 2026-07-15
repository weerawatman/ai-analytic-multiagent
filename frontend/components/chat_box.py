import streamlit as st


def render_chat_message(role: str, content: str, agent: str | None = None) -> None:
    """Render a single chat message with optional agent label."""
    with st.chat_message(role):
        if agent:
            st.caption(f"Agent: {agent}")
        st.markdown(content)
