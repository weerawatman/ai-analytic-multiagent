import streamlit as st

from components.api_client import get_json

ROLE_ORDER = [
    ("data_engineer", "🔧 Data Engineer"),
    ("data_analyst", "📈 Data Analyst"),
    ("data_scientist", "🧪 Data Scientist"),
    ("business_analyst", "💼 Business Analyst"),
]


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

    status = data.get("status", "pending")
    icon = {"completed": "✅", "running": "⏳", "failed": "❌"}.get(status, "⏸")
    st.caption(f"{icon} สถานะ: {status} · {data.get('onboarded_at', '')[:19]}")

    if data.get("team_summary"):
        st.markdown(data["team_summary"][:1500])

    if data.get("recommended_tables"):
        st.caption("ตารางแนะนำ: " + ", ".join(data["recommended_tables"][:5]))
    if data.get("key_metrics"):
        st.caption("Metrics: " + ", ".join(data["key_metrics"][:5]))

    consultant_notes = data.get("consultant_notes") or []
    if consultant_notes:
        with st.expander(f"🎓 คำแนะนำที่ปรึกษา (Claude) — {len(consultant_notes)} รายการ", expanded=True):
            for n in consultant_notes[-3:]:
                at = (n.get("at") or "")[:19]
                note = n.get("note") or ""
                st.caption(at)
                st.markdown(note[:1500])
                if len(note) > 1500:
                    st.caption("…(ตัดความยาว — ดูเต็มในไฟล์ team memory)")

    roles = data.get("roles", {})
    for role_key, label in ROLE_ORDER:
        entry = roles.get(role_key, {})
        summary = entry.get("handoff_summary", "")
        role_status = entry.get("status", "pending")
        with st.expander(f"{label} — {role_status}"):
            if summary:
                st.markdown(summary[:1200])
            else:
                st.caption("ยังไม่มี handoff — รอ onboarding หรือ re-run theme")
            notes = entry.get("feedback_notes") or []
            if notes:
                st.caption("CEO feedback:")
                for n in notes[-3:]:
                    st.markdown(f"- [{n.get('action')}] {n.get('comment', '')}")


def _render_role_placeholders() -> None:
    for _, label in ROLE_ORDER:
        with st.expander(f"{label} — รอ onboarding"):
            st.caption("เลือก theme แล้วรอทีมทำการบ้าน (DE → DA → DS → BA)")
