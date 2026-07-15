import streamlit as st

from components.api_client import get_json, patch_json

STATUS_OPTIONS = ["new", "discussing", "validated", "rejected", "promoted"]
STATUS_LABELS = {
    "new": "ใหม่",
    "discussing": "กำลังคุย BA/DA",
    "validated": "validate แล้ว",
    "rejected": "ทิ้ง",
    "promoted": "promote แล้ว",
}


def render_backlog_panel() -> None:
    """Sidebar backlog list with feedback and status update."""
    st.subheader("Insight Backlog")

    try:
        items = get_json("/api/v1/backlog/")
    except Exception as exc:
        st.caption(f"โหลด backlog ไม่ได้: {exc}")
        return

    if not items:
        st.caption("ยังไม่มี insight candidate — บันทึกจากแชทใน sprint ถัดไป")
        return

    st.caption(f"{len(items)} รายการ")
    for item in items[:20]:
        icon = {"new": "🆕", "discussing": "💬", "validated": "✅", "rejected": "❌", "promoted": "⭐"}.get(
            item.get("status", "new"), "📌"
        )
        title = item.get("question_th") or item.get("id", "")[:8]
        with st.expander(f"{icon} {title[:40]}"):
            st.markdown(f"**Theme:** {item.get('theme') or '-'}")
            st.markdown(f"**สถานะ:** {STATUS_LABELS.get(item.get('status', 'new'), item.get('status'))}")
            if item.get("answer_summary_th"):
                st.markdown(item["answer_summary_th"])
            if item.get("sql_primary"):
                st.code(item["sql_primary"], language="sql")

            feedback_key = f"feedback_{item['id']}"
            status_key = f"status_{item['id']}"
            feedback = st.text_area("Feedback จาก BA/DA", key=feedback_key, height=80)
            new_status = st.selectbox(
                "อัปเดตสถานะ",
                options=STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(item.get("status", "new")),
                format_func=lambda s: STATUS_LABELS.get(s, s),
                key=status_key,
            )
            if st.button("บันทึก", key=f"save_{item['id']}"):
                payload: dict = {"status": new_status}
                if feedback.strip():
                    payload["feedback"] = feedback.strip()
                try:
                    patch_json(f"/api/v1/backlog/{item['id']}", payload)
                    st.success("บันทึกแล้ว")
                    st.rerun()
                except Exception as exc:
                    st.error(f"บันทึกไม่สำเร็จ: {exc}")

            if item.get("ba_da_feedback"):
                st.markdown("**ประวัติ feedback**")
                for fb in item["ba_da_feedback"]:
                    st.caption(f"{fb.get('at', '')}: {fb.get('note', '')}")
