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
    """Show active data source (Fabric primary / Postgres fallback / offline) in sidebar."""
    st.subheader("แหล่งข้อมูล (Data Source)")
    try:
        data = get_json_allow_error("/api/v1/fabric/sources")
        active = data.get("active_source", "offline")
        fabric = data.get("fabric") or {}
        pg = data.get("postgres_replica") or {}

        if active == "fabric":
            st.success(f"🟦 Fabric DW · {fabric.get('database') or ''}")
        elif active == "postgres":
            st.warning(
                "🟨 **ใช้ฐานข้อมูลสำรอง (Postgres mirror)**\n\n"
                f"{data.get('detail_th', '')}\n\n"
                "ผลลัพธ์จะติดป้ายแหล่งข้อมูลกำกับเสมอ — เมื่อ Fabric กลับมา "
                "ระบบสลับกลับให้อัตโนมัติ"
            )
        elif fabric.get("configured") or pg.get("configured"):
            st.warning(
                "⚪ **โหมด Offline** — Fabric และ Postgres mirror ไม่พร้อมทั้งคู่\n\n"
                f"{data.get('detail_th', '')}\n\n"
                "ยังใช้ได้: Explore จาก discovery บนดิสก์ · draft SQL "
                "(ข้ามรันต่อคลัง) · Consultant · Team Memory / Knowledge"
            )
        else:
            st.warning("ยังไม่ได้ตั้งค่า Fabric / PG_REPLICA ใน .env")
    except httpx.ConnectError:
        st.error("Backend ไม่พร้อม — รัน .\\scripts\\run-backend.ps1 ก่อน")
    except Exception as exc:
        st.error(f"ตรวจสอบแหล่งข้อมูลไม่ได้: {exc}")


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
