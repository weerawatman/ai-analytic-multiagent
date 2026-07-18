"""Proactive insight feed (Phase I) — Streamlit multipage.

Reads via ``st.cache_data(ttl=30)`` per roadmap INV-12 (no new fragment poll);
the user refreshes the page or clicks "ตรวจสถานะงาน" to see a running job.
"""

from __future__ import annotations

import streamlit as st

from components.api_client import get_json, post_json

st.title("💡 Insights")
st.caption("สิ่งที่ระบบตรวจพบเองจากข้อมูล — GA Insights-style, ทุกตัวเลขมาจาก evidence จริง")

SOURCE_LABELS = {
    "fabric": "🟦 Fabric",
    "postgres": "🟨 Postgres mirror",
    "offline": "⚪ Offline",
}
DIRECTION_ICONS = {"up": "⬆️", "down": "⬇️", "flat": "➡️"}
DETECTOR_LABELS_TH = {
    "anomaly": "ความผิดปกติ",
    "changepoint": "จุดเปลี่ยนระดับ",
    "trend": "แนวโน้ม",
    "forecast_residual": "หลุดพยากรณ์",
}


@st.cache_data(ttl=30)
def _fetch_insights(status: str) -> list[dict]:
    try:
        data = get_json(f"/api/v1/insights/?status={status}&limit=50")
        return data.get("items", [])
    except Exception:
        return []


@st.cache_data(ttl=30)
def _fetch_status() -> dict:
    try:
        return get_json("/api/v1/insights/status")
    except Exception:
        return {}


col1, col2 = st.columns([3, 1])
with col1:
    status_data = _fetch_status()
    counts = status_data.get("status_counts", {})
    feedback = status_data.get("feedback", {})
    st.caption(
        f"เผยแพร่แล้ว {counts.get('published', 0)} · "
        f"รอ narrate {counts.get('scored', 0)} · ถูกซ่อน {counts.get('suppressed', 0)} · "
        f"feedback รวม {feedback.get('total', 0)} "
        f"(มีประโยชน์ {feedback.get('useful_pct', 0)}% · ข้อมูลผิด {feedback.get('wrong_pct', 0)}%)"
    )
with col2:
    if st.button("🔄 รันเดี๋ยวนี้", use_container_width=True):
        try:
            job = post_json("/api/v1/insights/refresh", {})
            st.session_state["insights_job_id"] = job["job_id"]
            st.success(f"ส่งงานแล้ว (job_id={job['job_id'][:8]})")
        except Exception as exc:
            st.error(f"ส่งงานไม่สำเร็จ: {exc}")

if st.session_state.get("insights_job_id"):
    if st.button("ตรวจสถานะงานล่าสุด"):
        try:
            job = get_json(f"/api/v1/jobs/{st.session_state['insights_job_id']}")
            st.info(f"สถานะ: {job.get('status')} — current step: {job.get('current_step') or '-'}")
            if job.get("status") == "done":
                _fetch_status.clear()
                _fetch_insights.clear()
        except Exception as exc:
            st.warning(f"ติดต่อ backend ไม่ได้: {exc}")

st.divider()

items = _fetch_insights("published")
if not items:
    st.info("ยังไม่มี insight ที่เผยแพร่ — กด 'รันเดี๋ยวนี้' หรือรอรอบอัตโนมัติ (ต้องเปิด INSIGHT_PIPELINE_ENABLED)")

for insight in items:
    direction_icon = DIRECTION_ICONS.get(insight.get("direction"), "")
    detector_th = DETECTOR_LABELS_TH.get(insight.get("detector"), insight.get("detector"))
    source_label = SOURCE_LABELS.get(insight.get("source") or "", "")
    with st.container(border=True):
        st.markdown(
            f"### {direction_icon} {insight['metric_key']} · {insight['period']} "
            f"— {detector_th}"
        )
        st.caption(
            f"impact={insight.get('impact', 0):.2f} · significance={insight.get('significance', 0):.2f} · "
            f"novelty={insight.get('novelty', 0):.2f} · score={insight.get('score', 0):.4f} · {source_label}"
        )
        st.markdown(insight.get("narrative_th") or "_(ไม่มี narrative)_")

        with st.expander("ดู evidence"):
            st.json(insight.get("evidence") or {})

        key_base = f"insight_fb_{insight['id']}"
        if st.session_state.get(f"{key_base}_done"):
            st.caption("บันทึก feedback แล้ว — ขอบคุณครับ")
        else:
            c1, c2, c3 = st.columns(3)
            label = None
            with c1:
                if st.button("👍 มีประโยชน์", key=f"{key_base}_useful"):
                    label = "useful"
            with c2:
                if st.button("👎 ไม่มีประโยชน์", key=f"{key_base}_not_useful"):
                    label = "not_useful"
            with c3:
                if st.button("⚠️ ข้อมูลผิด", key=f"{key_base}_wrong"):
                    label = "wrong"
            if label:
                try:
                    post_json(f"/api/v1/insights/{insight['id']}/feedback", {"label": label})
                    st.session_state[f"{key_base}_done"] = True
                    st.rerun()
                except Exception as exc:
                    st.error(f"บันทึก feedback ไม่สำเร็จ: {exc}")
