import streamlit as st


def render_mode_badge(mode: str) -> None:
    if mode == "trusted":
        st.markdown("🟢 **Trusted** — ใช้นิยามที่ approve แล้ว")
    else:
        st.markdown("🟡 **Draft · Explore** — รอ validate กับ BA/DA")


def render_assistant_message(content: str, agent: str, mode: str) -> None:
    render_mode_badge(mode)
    st.markdown(f"**[{agent}]**")
    st.markdown(content)
