import os
import uuid
from datetime import datetime, timezone

import httpx
import streamlit as st

from components.api_client import find_active_job, get_job, get_json, post_json, submit_chat_job
from components.approval_panel import render_approval_panel
from components.backlog_panel import render_backlog_panel
from components.ceo_briefing_panel import render_ceo_briefing_panel
from components.team_memory_panel import render_team_memory_panel
from components.consultant_panel import render_consultant_panel
from components.chat_box import render_answer_rating, render_assistant_message
from components.knowledge_panel import render_knowledge_panel
from components.promotion_panel import render_promotion_panel
from components.status_bar import render_fabric_status, render_mode_selector
from components.validation_panel import render_validation_panel

DEFAULT_TIMEOUT = float(
    os.getenv("FRONTEND_HTTP_TIMEOUT") or os.getenv("COMPOSE_HTTP_TIMEOUT", "600")
)

st.set_page_config(
    page_title="AI Fabric Insight Explorer",
    page_icon="📊",
    layout="wide",
)

st.title("📊 AI Fabric Insight Explorer")
st.caption("Local AI Data Team — Explore · Backlog · Trusted")

STEP_LABELS = {
    "prepare_context": "📋 เตรียมบริบท",
    "router": "🧭 Router",
    "de_context": "🔧 Data Engineer",
    "data_engineer": "🔧 Data Engineer",
    "explore_critique": "🧪 Data Scientist",
    "data_scientist": "🧪 Data Scientist",
    "data_analyst": "📈 Data Analyst",
    "business_analyst": "💼 Business Analyst",
    "quality_assembly": "✅ Quality Check",
    "summarize": "📝 สรุปคำตอบ",
    "approval_gate": "🚦 รออนุมัติ",
    "consultant_review": "🎓 ที่ปรึกษา (Claude)",
    "consultant_coach": "🎓 โค้ชทีม (Claude)",
    "consult": "🎓 ปรึกษา Claude",
    "onboarding": "🧠 Onboarding",
    "deep_profile": "🔬 Data Homework (profiling จริง)",
    "starter_pack": "💡 Insight Starter Pack",
}


def _load_history(thread_id: str) -> list[dict]:
    """Reload chat history from the backend so answers survive refresh/timeouts."""
    try:
        raw = get_json(f"/api/v1/sessions/{thread_id}/messages")
    except Exception:
        return []
    messages: list[dict] = []
    for m in raw:
        entry = {"role": m["role"], "content": m["content"]}
        if m["role"] == "assistant":
            entry["agent"] = m.get("agent") or "agent"
            entry["mode"] = st.session_state.get("mode", "explore")
        messages.append(entry)
    return messages


def _handle_finished_job(job: dict) -> None:
    """Append the finished job's answer/error to the conversation exactly once."""
    if job["id"] in st.session_state.handled_job_ids:
        return
    st.session_state.handled_job_ids.add(job["id"])
    st.session_state.active_job_id = None

    status = job.get("status")
    if status == "done":
        result = job.get("result") or {}
        content = result.get("content") or "(ไม่มีเนื้อหาตอบกลับ)"
        agent = result.get("agent") or "ai_data_team"
        agents_involved = result.get("agents_involved") or []
        st.session_state.last_quality_payload = result.get("quality_payload")
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": content,
                "agent": agent,
                "mode": st.session_state.get("mode", "explore"),
                "agents_involved": agents_involved,
            }
        )
        if result.get("requires_approval"):
            st.session_state.pending_approval = True
    elif status == "cancelled":
        st.session_state.messages.append(
            {"role": "assistant", "content": "❌ ยกเลิกคำถามนี้แล้ว", "mode": st.session_state.get("mode", "explore")}
        )
    else:
        error = job.get("error") or "ไม่ทราบสาเหตุ — ดู log ที่ data/local/logs/backend.log"
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": f"เกิดข้อผิดพลาดระหว่างประมวลผล: {error}",
                "mode": st.session_state.get("mode", "explore"),
            }
        )


def _elapsed_minutes(started_at: str | None) -> str:
    if not started_at:
        return ""
    try:
        started = datetime.fromisoformat(started_at)
        minutes = (datetime.now(timezone.utc) - started).total_seconds() / 60
        return f" · ผ่านไป {minutes:.0f} นาที"
    except ValueError:
        return ""


def _step_elapsed(entry: dict) -> str:
    started = entry.get("started_at")
    ended = entry.get("ended_at")
    if not started:
        return ""
    try:
        t0 = datetime.fromisoformat(started)
        t1 = datetime.fromisoformat(ended) if ended else datetime.now(timezone.utc)
        secs = max(0, (t1 - t0).total_seconds())
        if secs < 60:
            return f" ({secs:.0f} วิ)"
        return f" ({secs / 60:.1f} นาที)"
    except ValueError:
        return ""


def _render_progress(job: dict) -> None:
    status = job.get("status")
    if status == "failed":
        st.error(f"❌ งานล้มเหลว: {job.get('error') or 'ไม่ทราบสาเหตุ'}")
        return

    health = job.get("health")
    age = job.get("heartbeat_age_s")
    age_txt = f"{age:.0f} วิที่แล้ว" if isinstance(age, (int, float)) else "—"
    if health == "stalled":
        st.warning(
            f"⚠️ ทีมอาจค้างหรือ backend ไม่ตอบ — heartbeat ล่าสุด {age_txt}"
            f"{_elapsed_minutes(job.get('started_at'))}"
        )
    else:
        st.success(
            f"✅ ทีมยังทำงานอยู่ (heartbeat {age_txt})"
            f"{_elapsed_minutes(job.get('started_at'))}"
        )

    done_steps = {p["step"]: p for p in job.get("progress", [])}
    current = job.get("current_step")
    for step, label in STEP_LABELS.items():
        if step in done_steps:
            entry = done_steps[step]
            icon = "✅" if entry["status"] == "done" else "⚠️"
            note = f" — {entry['note']}" if entry.get("note") else ""
            st.markdown(f"{icon} {label}{_step_elapsed(entry)}{note}")
        elif step == current:
            entry = done_steps.get(step) or {}
            note = f" — {entry['note']}" if entry.get("note") else ""
            st.markdown(f"⏳ {label} ← กำลังทำงาน{_step_elapsed(entry)}{note}")
    st.caption("ปิดแท็บ/refresh ได้ ระบบทำงานต่อเบื้องหลัง — กลับมาดูด้วย thread เดิมได้เสมอ")


@st.fragment(run_every=3)
def poll_active_job() -> None:
    job_id = st.session_state.get("active_job_id")
    if not job_id:
        return
    try:
        job = get_job(job_id)
    except Exception as exc:
        st.warning(f"⚠️ ติดต่อ backend ไม่ได้ (จะลองใหม่อัตโนมัติ): {exc}")
        return
    if job.get("status") in ("queued", "running"):
        _render_progress(job)
        return
    if job.get("status") == "failed":
        _render_progress(job)
    _handle_finished_job(job)
    st.rerun(scope="app")


def _submit_question(prompt: str, mode: str, theme: str | None, theme_id: str | None) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt})
    try:
        data = submit_chat_job(
            {
                "thread_id": st.session_state.thread_id,
                "message": prompt,
                "mode": mode,
                "theme": theme,
                "theme_id": theme_id,
            }
        )
        st.session_state.active_job_id = data["job_id"]
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            detail = None
            try:
                detail = e.response.json().get("detail")
            except Exception:
                pass
            if isinstance(detail, dict) and detail.get("job_id"):
                st.session_state.active_job_id = detail["job_id"]
                st.warning("ยังประมวลผลคำถามก่อนหน้าอยู่ — ติดตามสถานะงานเดิมต่อ")
            else:
                st.error("ยังประมวลผลคำถามก่อนหน้าอยู่ — รอให้เสร็จก่อนถามใหม่")
        else:
            st.error(f"Backend error {e.response.status_code}: {e.response.text[:200]}")
    except httpx.HTTPError as e:
        st.error(f"เชื่อมต่อ backend ไม่สำเร็จ: {e}")


# ──── Session State ────
if "thread_id" not in st.session_state:
    st.session_state.thread_id = st.query_params.get("thread") or str(uuid.uuid4())[:8]
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
if "active_job_id" not in st.session_state:
    st.session_state.active_job_id = None
if "handled_job_ids" not in st.session_state:
    st.session_state.handled_job_ids = set()
if "loaded_thread" not in st.session_state:
    st.session_state.loaded_thread = None

# Keep thread id in the URL so a browser refresh returns to the same conversation.
if st.query_params.get("thread") != st.session_state.thread_id:
    st.query_params["thread"] = st.session_state.thread_id

# On first load (or thread switch): restore history + re-attach to a running job.
if st.session_state.loaded_thread != st.session_state.thread_id:
    st.session_state.loaded_thread = st.session_state.thread_id
    st.session_state.messages = _load_history(st.session_state.thread_id)
    st.session_state.active_job_id = None
    try:
        active = find_active_job(st.session_state.thread_id)
        if active:
            st.session_state.active_job_id = active["id"]
    except Exception:
        pass

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
        st.rerun()

    if st.button("เริ่มบทสนทนาใหม่"):
        st.session_state.thread_id = str(uuid.uuid4())[:8]
        st.session_state.messages = []
        st.session_state.pending_approval = False
        st.session_state.active_job_id = None
        st.session_state.loaded_thread = st.session_state.thread_id
        st.query_params["thread"] = st.session_state.thread_id
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
        render_consultant_panel()
        render_ceo_briefing_panel()
with col_mode:
    if st.session_state.mode == "explore":
        st.markdown("### 🟡 Explore")
    else:
        st.markdown("### 🟢 Trusted")

# ──── Chat History ────
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and msg.get("mode"):
            render_assistant_message(
                msg["content"],
                msg.get("agent", "agent"),
                msg["mode"],
                msg.get("agents_involved"),
            )
            # Rate only the latest completed assistant answer when idle
            if (
                not st.session_state.active_job_id
                and idx == len(st.session_state.messages) - 1
            ):
                render_answer_rating(
                    session_id=st.session_state.thread_id,
                    message_index=idx,
                    job_id=msg.get("job_id"),
                )
        else:
            st.markdown(msg["content"])

# ──── Active job progress (polls every 3s; survives refresh via re-attach) ────
if st.session_state.active_job_id:
    with st.chat_message("assistant"):
        poll_active_job()

# ──── Approval / Promotion Panels ────
if st.session_state.pending_approval:
    render_approval_panel()

if st.session_state.get("promotion_preview"):
    render_promotion_panel()

# ──── Chat Input ────
if not st.session_state.active_job_id:
    if prompt := st.chat_input("ถามทีมข้อมูลของคุณ..."):
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

        _submit_question(prompt, mode, theme, theme_id)
        st.rerun()
