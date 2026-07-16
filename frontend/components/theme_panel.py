import streamlit as st
from urllib.parse import quote

from components.api_client import ONBOARDING_TIMEOUT, get_json, post_json


def render_theme_panel() -> None:
    """Schema scan and theme selection for Explore."""
    st.subheader("Theme สำรวจ")

    if st.button("🔍 สแกน Schema", use_container_width=True):
        with st.spinner("กำลังสแกน Fabric DW... (อาจใช้เวลา)"):
            try:
                data = post_json("/api/v1/themes/scan?use_llm=true", {})
                st.session_state.themes_data = data
                st.success(f"พบ {len(data.get('themes', []))} themes")
                st.rerun()
            except Exception as exc:
                st.error(f"สแกนไม่สำเร็จ: {exc}")

    themes_data = st.session_state.get("themes_data")
    if not themes_data:
        try:
            themes_data = get_json("/api/v1/themes/")
            if themes_data.get("themes"):
                st.session_state.themes_data = themes_data
        except Exception:
            themes_data = {"themes": []}

    themes = themes_data.get("themes", []) if themes_data else []
    if not themes:
        st.caption("ยังไม่มี theme — กดสแกน Schema เพื่อเริ่ม Explore")
        return

    if themes_data.get("scanned_at"):
        st.caption(f"สแกนล่าสุด: {themes_data['scanned_at'][:19]}")

    for theme in themes:
        selected = st.session_state.get("selected_theme_id") == theme["id"]
        label = f"{'✅ ' if selected else ''}{theme['name_th']} ({theme.get('table_count', 0)} ตาราง)"
        with st.expander(label, expanded=selected):
            st.markdown(theme.get("rationale_th", ""))
            if theme.get("sample_tables"):
                st.caption("ตัวอย่าง: " + ", ".join(theme["sample_tables"][:4]))
            st.markdown("**คำถามเริ่มต้น**")
            for q in theme.get("starter_questions_th", []):
                st.markdown(f"- {q}")
            if st.button("เลือก Theme นี้", key=f"pick_theme_{theme['id']}"):
                st.session_state.selected_theme_id = theme["id"]
                st.session_state.theme_input = theme["name_th"]
                st.session_state.selected_theme = theme
                _run_discovery_and_onboarding(theme)
                st.rerun()

    if st.session_state.get("selected_theme"):
        st.info(f"Theme ที่เลือก: **{st.session_state.theme_input}**")
        disc = st.session_state.get("discovery_status")
        if disc:
            st.caption(disc)


def _run_discovery_and_onboarding(theme: dict) -> None:
    theme_id = theme["id"]
    theme_name = theme.get("name_th", "")
    with st.spinner("ทีมกำลังเรียนรู้ข้อมูล... (Discovery + Onboarding — อาจใช้เวลา 20-40 นาที)"):
        try:
            result = post_json(f"/api/v1/discovery/{theme_id}/run", {}, timeout=ONBOARDING_TIMEOUT)
            tables = result.get("tables_profiled", 0)
            st.session_state.discovery_status = f"Discovery: {tables} ตาราง profile แล้ว"
            try:
                name_q = quote(theme_name)
                post_json(f"/api/v1/briefings/{theme_id}/generate?theme_name={name_q}", {}, timeout=ONBOARDING_TIMEOUT)
            except Exception:
                pass
            try:
                onboard = post_json(
                    f"/api/v1/onboarding/{theme_id}/run?theme_name={quote(theme_name)}",
                    {},
                    timeout=ONBOARDING_TIMEOUT,
                )
                st.session_state.discovery_status += (
                    f" · Onboarding: {onboard.get('status', 'done')}"
                )
            except Exception as exc:
                st.session_state.discovery_status += f" · Onboarding: ล้มเหลว ({exc})"
        except Exception as exc:
            st.session_state.discovery_status = f"Discovery ล้มเหลว: {exc}"
