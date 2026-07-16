import os
import uuid

import httpx
import streamlit as st

from components.api_client import CHAT_TIMEOUT, get_json, post_json
from components.approval_panel import render_approval_panel
from components.backlog_panel import render_backlog_panel
from components.ceo_briefing_panel import render_ceo_briefing_panel
from components.team_memory_panel import render_team_memory_panel
from components.chat_box import render_assistant_message
from components.knowledge_panel import render_knowledge_panel
from components.promotion_panel import render_promotion_panel
from components.status_bar import render_fabric_status, render_mode_selector
from components.validation_panel import render_validation_panel

DEFAULT_TIMEOUT = float(os.getenv("COMPOSE_HTTP_TIMEOUT", "600"))

st.set_page_config(
    page_title="AI Fabric Insight Explorer",
    page_icon="📊",
    layout="wide",
)

st.title("📊 AI Fabric Insight Explorer")
st.caption("Local AI Data Team — Explore · Backlog · Trusted")


def _execute_chat_request(prompt: str, mode: str, theme: str | None, theme_id: str | None) -> None:
    """Call backend and persist assistant message in session state."""
    with st.status(
        "ทีมกำลังทำงาน: 🔧 DE → 📈 DA → 🧪 DS → 💼 BA (อาจใช้เวลา 15–45 นาที)",
        expanded=True,
    ) as status:
        st.write("อย่าปิดแท็บหรือถามซ้ำ — รอจน status ขึ้น 'เสร็จแล้ว'")
        try:
            data = post_json(
                "/api/v1/chat/",
                {
                    "thread_id": st.session_state.thread_id,
                    "message": prompt,
                    "mode": mode,
                    "theme": theme,
                    "theme_id": theme_id,
                },
                timeout=CHAT_TIMEOUT,
            )
            status.update(label="เสร็จแล้ว", state="complete")

            agent = data["agent"]
            content = data.get("content") or "(ไม่มีเนื้อหาตอบกลับ)"
            agents_involved = data.get("agents_involved") or []
            quality_payload = data.get("quality_payload")
            st.session_state.last_quality_payload = quality_payload

            render_assistant_message(content, agent, mode, agents_involved)

            if quality_payload and mode == "explore":
                gaps = quality_payload.get("quality_gaps") or data.get("quality_gaps")
                if gaps:
                    st.warning(f"Quality Bar D ยังขาด: {', '.join(gaps)}")

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": content,
                    "agent": agent,
                    "mode": mode,
                    "agents_involved": agents_involved,
                }
            )

            if data.get("requires_approval"):
                st.session_state.pending_approval = True

        except httpx.TimeoutException:
            status.update(label="Frontend timeout — backend อาจยังทำงานอยู่", state="error")
            mins = int(CHAT_TIMEOUT // 60)
            error_msg = (
                f"รอคำตอบเกิน {mins} นาที — อย่าถามซ้ำ ลอง refresh หลัง 5 นาที "
                "หรือเริ่ม thread ใหม่"
            )
            st.error(error_msg)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_msg, "mode": mode}
            )
        except httpx.HTTPStatusError as e:
            status.update(label="เกิดข้อผิดพลาด", state="error")
            if e.response.status_code == 409:
                error_msg = "ยังประมวลผลคำถามก่อนหน้าอยู่ — รอให้เสร็จก่อนถามใหม่"
            else:
                detail = e.response.text[:200]
                error_msg = f"Backend error {e.response.status_code}: {detail}"
            st.error(error_msg)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_msg, "mode": mode}
            )
        except httpx.HTTPError as e:
            status.update(label="เกิดข้อผิดพลาด", state="error")
            error_msg = f"เชื่อมต่อ backend ไม่สำเร็จ: {e}"
            st.error(error_msg)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_msg, "mode": mode}
            )
        finally:
            st.session_state.chat_processing = False
            st.session_state.pending_chat = None


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
if "promotion_preview" not in st.session_state:
    st.session_state.promotion_preview = None
if "chat_processing" not in st.session_state:
    st.session_state.chat_processing = False
if "pending_chat" not in st.session_state:
    st.session_state.pending_chat = None

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
        st.session_state.chat_processing = False
        st.session_state.pending_chat = None
        st.rerun()

    st.divider()
    render_backlog_panel()

    st.divider()
    render_validation_panel()

    if st.session_state.get("last_quality_payload"):
        st.divider()
        st.subheader("บันทึก Insight")
        if st.button("💾 บันทึก Candidate ล่าสุด", use_container_width=True):
            try:
                post_json("/api/v1/chat/save-candidate", st.session_state.last_quality_payload)
                st.success("บันทึก backlog แล้ว")
                st.session_state.last_quality_payload = None
                st.rerun()
            except Exception as exc:
                st.error(f"บันทึกไม่สำเร็จ: {exc}")

    st.divider()
    render_knowledge_panel()

    st.divider()
    st.markdown("**Agents**")
    st.caption("🔧 DE · 📈 Analyst · 🧪 Scientist · 💼 BA")

# ──── Main: current mode indicator ────
col_main, col_mode = st.columns([4, 1])
with col_main:
    if st.session_state.get("selected_theme_id"):
        render_team_memory_panel()
        render_ceo_briefing_panel()
with col_mode:
    if st.session_state.mode == "explore":
        st.markdown("### 🟡 Explore")
    else:
        st.markdown("### 🟢 Trusted")

if st.session_state.chat_processing:
    st.info("⏳ กำลังประมวลผลคำถาม — อย่าถามซ้ำหรือเปลี่ยน thread (รอ 15–45 นาที)")

# ──── Chat History ────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and msg.get("mode"):
            render_assistant_message(
                msg["content"],
                msg.get("agent", "agent"),
                msg["mode"],
                msg.get("agents_involved"),
            )
        else:
            st.markdown(msg["content"])

# ──── Resume in-flight request (survives Streamlit reruns) ────
if st.session_state.chat_processing and st.session_state.pending_chat:
    pending = st.session_state.pending_chat
    with st.chat_message("assistant"):
        _execute_chat_request(
            pending["prompt"],
            pending["mode"],
            pending.get("theme"),
            pending.get("theme_id"),
        )
    if st.session_state.pending_approval:
        st.rerun()

# ──── Approval / Promotion Panels ────
if st.session_state.pending_approval:
    render_approval_panel()

if st.session_state.get("promotion_preview"):
    render_promotion_panel()

# ──── Chat Input ────
if not st.session_state.chat_processing:
    if prompt := st.chat_input(
        "ถามทีมข้อมูลของคุณ...",
        disabled=st.session_state.chat_processing,
    ):
        mode = st.session_state.get("mode", "explore")
        theme = st.session_state.get("theme_input") or None
        theme_id = st.session_state.get("selected_theme_id") or None

        if mode == "trusted":
            try:
                trusted = get_json("/api/v1/semantic/trusted")
                if not (trusted.get("metrics") or []):
                    st.warning(
                        "Trusted mode ยังไม่มี metric — สลับเป็น Explore หรือ promote จาก backlog ก่อน"
                    )
            except Exception:
                pass

        if not theme_id:
            st.warning("แนะนำ: เลือก Theme ใน sidebar ก่อน (เช่น ฐานข้อมูล SAP HANA สำหรับ CE1SATG)")

        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.pending_chat = {
            "prompt": prompt,
            "mode": mode,
            "theme": theme,
            "theme_id": theme_id,
        }
        st.session_state.chat_processing = True
        st.rerun()
