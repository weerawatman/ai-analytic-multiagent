import httpx
import streamlit as st

from components.api_client import get_json, post_json


def render_promotion_panel() -> None:
    """HITL panel for Trusted promotion from backlog."""
    preview = st.session_state.get("promotion_preview")
    if not preview:
        return

    st.warning("⭐ Promote to Trusted — ตรวจ preview ก่อน Approve")

    metric = preview.get("metric", {})
    st.markdown(preview.get("preview_markdown", ""))

    with st.expander("แก้ไขก่อน promote (optional)"):
        metric_key = st.text_input("Metric key", value=metric.get("metric_key", ""), key="promo_key")
        display_name = st.text_input(
            "Display name (TH)", value=metric.get("display_name_th", ""), key="promo_name"
        )
        definition = st.text_area(
            "Business definition (TH)",
            value=metric.get("business_definition_th", ""),
            key="promo_def",
            height=100,
        )
        playbook = st.text_area(
            "Playbook (TH)", value=metric.get("playbook_th", ""), key="promo_playbook", height=100
        )
        example_q = st.text_area(
            "Example questions (one per line)",
            value="\n".join(metric.get("example_questions_th") or []),
            key="promo_questions",
            height=80,
        )

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("✅ Approve Trusted", type="primary", use_container_width=True):
            _handle_promotion(
                item_id=preview["item_id"],
                approved=True,
                metric_key=metric_key,
                display_name_th=display_name,
                business_definition_th=definition,
                playbook_th=playbook,
                example_questions_th=[q.strip() for q in example_q.splitlines() if q.strip()],
            )
    with col2:
        if st.button("❌ Reject", use_container_width=True):
            _handle_promotion(item_id=preview["item_id"], approved=False)
    with col3:
        if st.button("ยกเลิก", use_container_width=True):
            st.session_state.promotion_preview = None
            st.rerun()


def _handle_promotion(
    item_id: str,
    approved: bool,
    metric_key: str = "",
    display_name_th: str = "",
    business_definition_th: str = "",
    playbook_th: str = "",
    example_questions_th: list[str] | None = None,
) -> None:
    payload: dict = {"approved": approved, "approved_by": "data_engineer"}
    if approved:
        payload.update(
            {
                "metric_key": metric_key or None,
                "display_name_th": display_name_th or None,
                "business_definition_th": business_definition_th or None,
                "playbook_th": playbook_th or None,
                "example_questions_th": example_questions_th or None,
            }
        )

    try:
        data = post_json(f"/api/v1/semantic/promote/{item_id}/approve", payload)
        if data.get("status") == "promoted":
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": f"**[Trusted]** Promoted `{data['metric']['metric_key']}` — พร้อมใช้ใน Trusted mode",
                    "mode": "trusted",
                }
            )
        else:
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": "**[Trusted]** Promotion cancelled — backlog unchanged",
                    "mode": "explore",
                }
            )
        st.session_state.promotion_preview = None
        st.rerun()
    except httpx.HTTPError as exc:
        st.error(f"Promotion failed: {exc}")


def load_promotion_preview(item_id: str) -> None:
    """Fetch preview from API and store in session."""
    preview = get_json(f"/api/v1/semantic/promote/{item_id}/preview")
    st.session_state.promotion_preview = preview
