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
