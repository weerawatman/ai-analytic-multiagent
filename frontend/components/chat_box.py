import streamlit as st

AGENT_LABELS = {
    "data_engineer": "🔧 DE",
    "data_analyst": "📈 DA",
    "data_scientist": "🧪 DS",
    "business_analyst": "💼 BA",
    "ai_data_team": "👥 AI Data Team",
    "consultant": "🎓 ที่ปรึกษา (Claude)",
}


def render_mode_badge(mode: str) -> None:
    if mode == "trusted":
        st.markdown("🟢 **Trusted** — ใช้นิยามที่ approve แล้ว")
    else:
        st.markdown("🟡 **Draft · Explore** — รอ validate กับ BA/DA")


def render_team_agents(agents_involved: list[str] | None) -> None:
    if not agents_involved:
        return
    labels = [AGENT_LABELS.get(a, a) for a in agents_involved]
    st.caption("ทีมที่ร่วมตอบ: " + " → ".join(labels))


def render_assistant_message(
    content: str,
    agent: str,
    mode: str,
    agents_involved: list[str] | None = None,
) -> None:
    render_mode_badge(mode)
    label = AGENT_LABELS.get(agent, agent)
    st.markdown(f"**[{label}]**")
    render_team_agents(agents_involved)
    st.markdown(content)


def render_answer_rating(
    *,
    session_id: str,
    message_index: int,
    job_id: str | None = None,
) -> None:
    """👍/👎 capture under a final assistant answer (Phase G1b)."""
    from components.api_client import post_json

    key_base = f"rating_{session_id}_{message_index}"
    if st.session_state.get(f"{key_base}_done"):
        st.caption("บันทึกคะแนนแล้ว — ขอบคุณครับ")
        return

    with st.expander("ให้คะแนนคำตอบนี้", expanded=False):
        c1, c2 = st.columns(2)
        rating = None
        with c1:
            if st.button("👍 มีประโยชน์", key=f"{key_base}_up"):
                rating = "up"
        with c2:
            if st.button("👎 ยังไม่ดี", key=f"{key_base}_down"):
                rating = "down"

        reason = st.selectbox(
            "เหตุผล (ถ้า 👎)",
            options=["", "wrong_number", "wrong_metric", "too_slow", "unclear"],
            format_func=lambda x: {
                "": "(ไม่ระบุ)",
                "wrong_number": "ตัวเลขผิด",
                "wrong_metric": "metric ผิด",
                "too_slow": "ช้าเกินไป",
                "unclear": "อธิบายไม่ชัด",
            }.get(x, x),
            key=f"{key_base}_reason",
        )
        comment = st.text_input("หมายเหตุ", key=f"{key_base}_comment")
        corrected = st.text_area("คำตอบที่ถูกต้อง (ถ้ามี)", key=f"{key_base}_corrected")

        if rating:
            payload = {
                "session_id": session_id,
                "rating": rating,
                "job_id": job_id,
                "reason_tag": reason or None,
                "comment": comment or None,
                "corrected_answer": corrected or None,
            }
            try:
                post_json("/api/v1/chat/rating", payload)
                st.session_state[f"{key_base}_done"] = True
                st.success("บันทึกคะแนนแล้ว")
                st.rerun()
            except Exception as exc:
                st.error(f"บันทึกไม่สำเร็จ: {exc}")
