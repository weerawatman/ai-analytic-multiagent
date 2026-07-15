import os
import uuid

import httpx
import streamlit as st

from components.api_client import post_json
from components.approval_panel import render_approval_panel
from components.backlog_panel import render_backlog_panel
from components.chat_box import render_assistant_message
from components.status_bar import render_fabric_status, render_mode_selector

DEFAULT_TIMEOUT = float(os.getenv("COMPOSE_HTTP_TIMEOUT", "600"))

st.set_page_config(
    page_title="AI Fabric Insight Explorer",
    page_icon="📊",
    layout="wide",
)

st.title("📊 AI Fabric Insight Explorer")
st.caption("Local AI Data Team — Explore · Backlog · Trusted")

# ──── Session State ────
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())[:8]
if "messages" not in st.session_state:
    st.session_state.messages: list[dict[str, str]] = []
if "pending_approval" not in st.session_state:
    st.session_state.pending_approval = False
if "mode" not in st.session_state:
    st.session_state.mode = "explore"
if "theme_input" not in st.session_state:
    st.session_state.theme_input = ""

# ──── Sidebar ────
with st.sidebar:
    render_fabric_status()
    st.divider()
    render_mode_selector()
    st.divider()

    st.header("การสนทนา")
    thread_val = st.text_input("Thread ID", value=st.session_state.thread_id, key="thread_input")
    if thread_val != st.session_state.thread_id:
        st.session_state.thread_id = thread_val

    if st.button("เริ่มบทสนทนาใหม่"):
        st.session_state.thread_id = str(uuid.uuid4())[:8]
        st.session_state.messages = []
        st.session_state.pending_approval = False
        st.rerun()

    st.divider()
    render_backlog_panel()

    st.divider()
    st.markdown("**Agents**")
    st.caption("🔧 DE · 📈 Analyst · 🧪 Scientist")

# ──── Main: current mode indicator ────
col_main, col_mode = st.columns([4, 1])
with col_mode:
    if st.session_state.mode == "explore":
        st.markdown("### 🟡 Explore")
    else:
        st.markdown("### 🟢 Trusted")

# ──── Chat History ────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and msg.get("mode"):
            render_assistant_message(msg["content"], msg.get("agent", "agent"), msg["mode"])
        else:
            st.markdown(msg["content"])

# ──── Approval Panel ────
if st.session_state.pending_approval:
    render_approval_panel()

# ──── Chat Input ────
if prompt := st.chat_input("ถามทีมข้อมูลของคุณ..."):
    mode = st.session_state.get("mode", "explore")
    theme = st.session_state.get("theme_input") or None

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("กำลังวิเคราะห์... (local LLM อาจใช้เวลา)", expanded=True) as status:
            st.write("Agent กำลังทำงาน — โฟกัสคุณภาพ output")
            try:
                data = post_json(
                    "/api/v1/chat/",
                    {
                        "thread_id": st.session_state.thread_id,
                        "message": prompt,
                        "mode": mode,
                        "theme": theme,
                    },
                )
                status.update(label="เสร็จแล้ว", state="complete")

                agent = data["agent"]
                content = data["content"]
                render_assistant_message(content, agent, mode)

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": content,
                        "agent": agent,
                        "mode": mode,
                    }
                )

                if data.get("requires_approval"):
                    st.session_state.pending_approval = True
                    st.rerun()

            except httpx.HTTPError as e:
                status.update(label="เกิดข้อผิดพลาด", state="error")
                error_msg = f"เชื่อมต่อ backend ไม่สำเร็จ: {e}"
                st.error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg, "mode": mode}
                )
