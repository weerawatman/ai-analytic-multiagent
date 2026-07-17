import streamlit as st
from urllib.parse import quote

from components.api_client import get_json, post_json

ROLE_ORDER = [
    ("data_engineer", "🔧 Data Engineer"),
    ("data_scientist", "🧪 Data Scientist"),
    ("data_analyst", "📈 Data Analyst"),
    ("business_analyst", "💼 Business Analyst"),
]


def _clip(value, n: int = 19) -> str:
    return (value or "")[:n]


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
        _render_empty_roles()
        return

    st.caption(f"สร้างเมื่อ: {_clip(data.get('generated_at'))}")

    briefs_by_role: dict[str, list] = {r: [] for r, _ in ROLE_ORDER}
    for brief in data.get("briefs", []):
        role = brief.get("role", "")
        if role in briefs_by_role:
            briefs_by_role[role].append(brief)

    for role_key, role_label in ROLE_ORDER:
        role_briefs = briefs_by_role.get(role_key, [])
        with st.expander(f"{role_label} ({len(role_briefs)} briefs)", expanded=bool(role_briefs)):
            if not role_briefs:
                st.caption("ยังไม่มี brief จาก role นี้ — รอ generate หลัง discovery")
                continue
            for brief in role_briefs:
                st.markdown(f"**{brief.get('title_th', role_key)}**")
                st.markdown(brief.get("summary_th", ""))
                st.caption(
                    f"Priority: {brief.get('priority', 'medium')} · "
                    f"Status: {brief.get('status', 'pending')}"
                )

                comment = st.text_input(
                    "CEO Comment",
                    key=f"ceo_c_{brief.get('id')}",
                )
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Approve", key=f"ceo_ok_{brief.get('id')}"):
                        _send_feedback(theme_id, brief, "approve", comment)
                with col2:
                    if st.button("❌ Reject", key=f"ceo_no_{brief.get('id')}"):
                        _send_feedback(theme_id, brief, "reject", comment)
                st.divider()


def _render_empty_roles() -> None:
    for _, role_label in ROLE_ORDER:
        with st.expander(f"{role_label} — รอ briefing"):
            st.caption("รัน discovery + briefings หลังเลือก theme")


def _send_feedback(theme_id: str, brief: dict, action: str, comment: str) -> None:
    theme_name = st.session_state.get("theme_input", "")
    try:
        q = f"?theme_name={quote(theme_name)}" if theme_name else ""
        result = post_json(
            f"/api/v1/feedback/{theme_id}{q}",
            {
                "brief_id": brief.get("id", ""),
                "role": brief.get("role", ""),
                "action": action,
                "comment": comment or "",
            },
        )
        routed = result.get("routed") or []
        msg = "บันทึก feedback แล้ว"
        if routed:
            msg += f" (อัปเดต: {', '.join(routed)})"
        st.success(msg)
        st.rerun()
    except Exception as exc:
        st.error(str(exc))
