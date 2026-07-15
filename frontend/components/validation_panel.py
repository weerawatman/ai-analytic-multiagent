import streamlit as st

from components.api_client import get_json


def render_validation_panel() -> None:
    """Phase 1 DoD checklist from validation API."""
    st.subheader("Phase 1 Validation")

    try:
        data = get_json("/api/v1/validation/phase1")
    except Exception as exc:
        st.caption(f"โหลด validation ไม่ได้: {exc}")
        return

    summary = data.get("summary", {})
    passed = summary.get("passed", 0)
    total = summary.get("total", 0)

    if summary.get("ready_for_signoff"):
        st.success(f"✅ พร้อม sign-off ({passed}/{total})")
    else:
        st.warning(f"⏳ ยังไม่ครบ ({passed}/{total})")

    for check in data.get("checks", []):
        icon = "✅" if check.get("passed") else "❌"
        with st.expander(f"{icon} {check.get('title', check.get('id'))}"):
            st.caption(check.get("detail", ""))
            if check.get("manual_note") and not check.get("passed"):
                st.info(check.get("manual_note"))

    st.caption(f"Sign-off doc: `{data.get('sign_off_doc', '')}`")
