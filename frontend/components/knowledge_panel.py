import streamlit as st

from components.api_client import get_json, post_json, patch_json


def render_knowledge_panel() -> None:
    """Knowledge layer — glossary, targets, relationships."""
    st.subheader("Knowledge")

    theme = st.session_state.get("theme_input") or ""

    tab1, tab2, tab3 = st.tabs(["Glossary", "Targets", "Relationships"])

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
