import os
import uuid

import httpx
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")

st.set_page_config(
    page_title="AI Analytics Data Team",
    page_icon="📊",
    layout="wide",
)

st.title("📊 AI Analytics Multi-Agent System")
st.caption("Enterprise AI Data Team — Data Engineer · Data Analyst · Data Scientist")

# ──── Session State ────
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())[:8]
if "messages" not in st.session_state:
    st.session_state.messages: list[dict[str, str]] = []
if "pending_approval" not in st.session_state:
    st.session_state.pending_approval = False

# ──── Sidebar ────
with st.sidebar:
    st.header("Settings")
    st.text_input("Thread ID", value=st.session_state.thread_id, key="thread_input")
    if st.button("New Conversation"):
        st.session_state.thread_id = str(uuid.uuid4())[:8]
        st.session_state.messages = []
        st.session_state.pending_approval = False
        st.rerun()

    st.divider()
    st.markdown("**Agents**")
    st.markdown("- 🔧 Data Engineer — Schema & Semantic Layer")
    st.markdown("- 📈 Data Analyst — Text-to-SQL & Analysis")
    st.markdown("- 🧪 Data Scientist — ML & Forecasting")

# ──── Chat History ────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ──── Approval Panel ────
if st.session_state.pending_approval:
    from components.approval_panel import render_approval_panel
    render_approval_panel()

# ──── Chat Input ────
if prompt := st.chat_input("Ask your data team anything..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Agents are working..."):
            try:
                response = httpx.post(
                    f"{BACKEND_URL}/api/v1/chat/",
                    json={
                        "thread_id": st.session_state.thread_id,
                        "message": prompt,
                    },
                    timeout=300.0,
                )
                response.raise_for_status()
                data = response.json()

                agent_label = f"**[{data['agent']}]**"
                content = f"{agent_label}\n\n{data['content']}"
                st.markdown(content)

                st.session_state.messages.append(
                    {"role": "assistant", "content": content}
                )

                if data.get("requires_approval"):
                    st.session_state.pending_approval = True
                    st.rerun()

            except httpx.HTTPError as e:
                error_msg = f"Error communicating with backend: {e}"
                st.error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )
