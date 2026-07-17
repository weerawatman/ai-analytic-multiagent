import streamlit as st

from components.api_client import get_json

ROLE_ORDER = [
    ("data_engineer", "🔧 Data Engineer"),
    ("data_scientist", "🧪 Data Scientist"),
    ("data_analyst", "📈 Data Analyst"),
    ("business_analyst", "💼 Business Analyst"),
]


def _clip(value, n: int = 19) -> str:
    """Safe prefix for display — keys may exist with explicit null."""
    return (value or "")[:n]


def render_team_memory_panel() -> None:
    """Show team onboarding memory per role."""
    theme_id = st.session_state.get("selected_theme_id")
    if not theme_id:
        return

    st.subheader("Team Memory")
    try:
        data = get_json(f"/api/v1/onboarding/{theme_id}")
    except Exception:
        st.caption("ยังไม่มี team onboarding — เลือก theme เพื่อรัน discovery + onboarding")
        _render_role_placeholders()
        return

    status = data.get("status") or "pending"
    icon = {"completed": "✅", "running": "⏳", "failed": "❌"}.get(status, "⏸")
    st.caption(f"{icon} สถานะ: {status} · {_clip(data.get('onboarded_at'))}")

    team_summary = data.get("team_summary") or ""
    if team_summary:
        st.markdown(team_summary[:1500])

    recommended = data.get("recommended_tables") or []
    if recommended:
        st.caption("ตารางแนะนำ: " + ", ".join(str(t) for t in recommended[:5]))
    metrics = data.get("key_metrics") or []
    if metrics:
        st.caption("Metrics: " + ", ".join(str(m) for m in metrics[:5]))

    consultant_notes = data.get("consultant_notes") or []
    if consultant_notes:
        with st.expander(f"🎓 คำแนะนำที่ปรึกษา (Claude) — {len(consultant_notes)} รายการ", expanded=True):
            for n in consultant_notes[-3:]:
                at = _clip((n or {}).get("at"))
                note = (n or {}).get("note") or ""
                st.caption(at)
                st.markdown(note[:1500])
                if len(note) > 1500:
                    st.caption("…(ตัดความยาว — ดูเต็มในไฟล์ team memory)")

    roles = data.get("roles") or {}
    for role_key, label in ROLE_ORDER:
        entry = roles.get(role_key) or {}
        summary = entry.get("handoff_summary") or ""
        role_status = entry.get("status") or "pending"
        with st.expander(f"{label} — {role_status}"):
            if summary:
                st.markdown(summary[:1200])
            else:
                st.caption("ยังไม่มี handoff — รอ onboarding หรือ re-run theme")
            notes = entry.get("feedback_notes") or []
            if notes:
                st.caption("CEO feedback:")
                for n in notes[-3:]:
                    st.markdown(f"- [{(n or {}).get('action')}] {(n or {}).get('comment') or ''}")


def _render_role_placeholders() -> None:
    for _, label in ROLE_ORDER:
        with st.expander(f"{label} — รอ onboarding"):
            st.caption("เลือก theme แล้วรอทีมทำการบ้าน (DE → DS → DA → BA)")
