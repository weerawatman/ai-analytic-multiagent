import httpx
import streamlit as st

from components.api_client import get_json, get_json_allow_error
from components.theme_panel import render_theme_panel


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
        data = get_json_allow_error("/api/v1/fabric/health")
        if data.get("connected"):
            st.success(f"เชื่อมต่อแล้ว · {data.get('database', '')}")
        elif data.get("configured"):
            detail = data.get("detail_th") or data.get("detail", "เชื่อมต่อไม่สำเร็จ")
            if "capacity" in str(data.get("detail", "")).lower():
                st.warning(f"Fabric capacity เต็มชั่วคราว — ลองใหม่ภายหลัง\n\n{detail}")
            else:
                st.error(detail)
        else:
            st.warning("ยังไม่ได้ตั้งค่า Fabric ใน .env")
    except httpx.ConnectError:
        st.error("Backend ไม่พร้อม — รัน .\\scripts\\run-backend.ps1 ก่อน")
    except Exception as exc:
        st.error(f"ตรวจสอบ Fabric ไม่ได้: {exc}")


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
        try:
            trusted = get_json("/api/v1/semantic/trusted")
            count = len(trusted.get("metrics") or [])
            st.caption(f"Trusted metrics: {count}")
        except Exception:
            pass

    render_theme_panel()
