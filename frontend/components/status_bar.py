import streamlit as st

from components.api_client import get_json


STATUS_ICONS = {
    "new": "🆕",
    "discussing": "💬",
    "validated": "✅",
    "rejected": "❌",
    "promoted": "⭐",
}


def render_fabric_status() -> None:
    """Show Fabric connection status in sidebar."""
    st.subheader("Fabric DW")
    try:
        data = get_json("/api/v1/fabric/health")
        if data.get("connected"):
            st.success(f"เชื่อมต่อแล้ว · {data.get('database', '')}")
        elif data.get("configured"):
            st.error(data.get("detail_th") or data.get("detail", "เชื่อมต่อไม่สำเร็จ"))
        else:
            st.warning("ยังไม่ได้ตั้งค่า Fabric ใน .env")
    except Exception as exc:
        st.error(f"Backend ไม่พร้อม: {exc}")


def render_mode_selector() -> None:
    """Explore / Trusted mode toggle."""
    st.subheader("โหมดการทำงาน")
    mode = st.radio(
        "Mode",
        options=["explore", "trusted"],
        format_func=lambda x: "🔍 Explore (Draft)" if x == "explore" else "✅ Trusted",
        horizontal=True,
        key="mode_selector",
    )
    st.session_state.mode = mode

    if mode == "explore":
        st.caption("ผลลัพธ์เป็น Draft — รอ validate กับ BA/DA")
    else:
        st.caption("ใช้นิยามที่ approve แล้วใน semantic layer")

    st.text_input("Theme (optional)", key="theme_input", placeholder="เช่น sales, inventory")
