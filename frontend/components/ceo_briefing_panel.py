import streamlit as st

from components.api_client import get_json, post_json


def render_ceo_briefing_panel() -> None:
    """CEO view — role briefs with approve/reject/comment."""
    theme_id = st.session_state.get("selected_theme_id")
    if not theme_id:
        return

    st.subheader("CEO Briefing")

    try:
        data = get_json(f"/api/v1/briefings/{theme_id}")
    except Exception:
        st.caption("ยังไม่มี briefing — เลือก theme เพื่อรัน discovery")
        return

    st.caption(f"สร้างเมื่อ: {data.get('generated_at', '')[:19]}")

    for brief in data.get("briefs", []):
        role = brief.get("role", "agent")
        icon = {
            "data_engineer": "🔧",
            "data_analyst": "📈",
            "data_scientist": "🧪",
            "business_analyst": "💼",
        }.get(role, "📌")
        with st.expander(f"{icon} {brief.get('title_th', role)}"):
            st.markdown(brief.get("summary_th", ""))
            st.caption(f"Priority: {brief.get('priority', 'medium')} · Status: {brief.get('status', 'pending')}")

            comment = st.text_input("CEO Comment", key=f"ceo_c_{brief.get('id')}")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Approve", key=f"ceo_ok_{brief.get('id')}"):
                    _send_feedback(theme_id, brief, "approve", comment)
            with col2:
                if st.button("❌ Reject", key=f"ceo_no_{brief.get('id')}"):
                    _send_feedback(theme_id, brief, "reject", comment)


def _send_feedback(theme_id: str, brief: dict, action: str, comment: str) -> None:
    try:
        post_json(
            f"/api/v1/feedback/{theme_id}",
            {
                "brief_id": brief.get("id", ""),
                "role": brief.get("role", ""),
                "action": action,
                "comment": comment or "",
            },
        )
        st.success("บันทึก feedback แล้ว")
        st.rerun()
    except Exception as exc:
        st.error(str(exc))
