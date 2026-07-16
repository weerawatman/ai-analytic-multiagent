import os

import streamlit as st

from components.api_client import get_json, post_json, patch_json

DEFAULT_SAP_CSV = os.path.join(
    os.path.expanduser("~"),
    "Downloads",
    "SAP_Table_Description.csv",
)


def render_knowledge_panel() -> None:
    """Knowledge layer — glossary, targets, relationships, SAP tables."""
    st.subheader("Knowledge")

    theme = st.session_state.get("theme_input") or ""

    tab1, tab2, tab3, tab4 = st.tabs(["Glossary", "Targets", "Relationships", "SAP Tables"])

    with tab1:
        _render_add_form(
            "glossary",
            theme,
            fields=[
                ("field_key", "Field key (e.g. VBRK.NETWR)"),
                ("table_name", "Table"),
                ("definition_th", "นิยามภาษาไทย"),
            ],
        )
        _render_items("glossary", theme)

    with tab2:
        _render_add_form(
            "targets",
            theme,
            fields=[
                ("name_th", "ชื่อ KPI/Target"),
                ("description_th", "คำอธิบาย / เป้าหมายการวิเคราะห์"),
            ],
        )
        _render_items("targets", theme)

    with tab3:
        _render_add_form(
            "relationships",
            theme,
            fields=[
                ("from_table", "From table"),
                ("to_table", "To table"),
                ("join_keys", "Join keys (e.g. KUNNR)"),
            ],
        )
        _render_items("relationships", theme)

    with tab4:
        _render_sap_tables_tab()


def _render_sap_tables_tab() -> None:
    st.caption("นำเข้า SAP DD02T (TABNAME + DDTEXT) จาก CSV — agent จะใช้คำอธิบายตารางใน discovery context")

    try:
        stats = get_json("/api/v1/knowledge/sap-tables/stats")
        st.info(
            f"โหลดแล้ว **{stats.get('table_count', 0):,}** ตาราง"
            + (f" · {stats['imported_at'][:19]}" if stats.get("imported_at") else "")
        )
        if stats.get("source_file"):
            st.caption(f"ไฟล์ล่าสุด: `{stats['source_file']}`")
    except Exception as exc:
        st.caption(f"ยังไม่มีข้อมูล SAP: {exc}")

    csv_path = st.text_input(
        "Path ไฟล์ CSV",
        value=DEFAULT_SAP_CSV,
        key="sap_csv_path",
    )
    if st.button("นำเข้า SAP Table Description", key="import_sap_tables"):
        with st.spinner("กำลัง import... (ไฟล์ใหญ่อาจใช้เวลา 2–5 นาที)"):
            try:
                result = post_json(
                    "/api/v1/knowledge/sap-tables/import",
                    {"csv_path": csv_path, "language": "E", "replace": True},
                )
                st.success(f"นำเข้า {result.get('imported', 0):,} แถว (ข้าม {result.get('skipped', 0):,})")
                st.rerun()
            except Exception as exc:
                st.error(f"Import ไม่สำเร็จ: {exc}")

    lookup_ref = st.text_input("ทดสอบ lookup", value="SAPHANADB.VBRK_All_Cleaned", key="sap_lookup")
    if lookup_ref:
        try:
            data = get_json(f"/api/v1/knowledge/sap-tables/lookup/{lookup_ref}")
            if data.get("matched"):
                st.success(f"{data['sap_tabname']}: {data['description']}")
            else:
                st.warning(f"ไม่พบคำอธิบายสำหรับ {lookup_ref}")
        except Exception as exc:
            st.caption(str(exc))


def _render_add_form(kind: str, theme: str, fields: list[tuple[str, str]]) -> None:
    with st.expander(f"เพิ่ม {kind}"):
        values = {}
        for key, label in fields:
            values[key] = st.text_input(label, key=f"kn_{kind}_{key}")
        if st.button("บันทึก", key=f"save_kn_{kind}"):
            payload = {k: v for k, v in values.items() if v.strip()}
            if theme:
                payload["theme"] = theme
            if payload:
                try:
                    post_json(f"/api/v1/knowledge/{kind}", payload)
                    st.success("บันทึกแล้ว")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))


def _render_items(kind: str, theme: str) -> None:
    try:
        path = f"/api/v1/knowledge/{kind}"
        items = get_json(path)
        if theme:
            items = [i for i in items if not i.get("theme") or i.get("theme") == theme]
        for item in items[:15]:
            label = (
                item.get("field_key")
                or item.get("name_th")
                or f"{item.get('from_table')}->{item.get('to_table')}"
            )
            with st.expander(f"{label} ({item.get('status', 'draft')})"):
                for k, v in item.items():
                    if k not in ("id", "created_at", "updated_at"):
                        st.caption(f"{k}: {v}")
                if item.get("status") == "draft" and st.button("Approve", key=f"appr_{kind}_{item['id']}"):
                    try:
                        patch_json(f"/api/v1/knowledge/{kind}/{item['id']}/approve", {})
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
    except Exception as exc:
        st.caption(f"โหลด {kind} ไม่ได้: {exc}")
