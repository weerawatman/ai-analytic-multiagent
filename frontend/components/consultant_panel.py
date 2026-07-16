"""Claude external consultant panel — on-demand consult for selected theme."""

from __future__ import annotations

import httpx
import streamlit as st

from components.api_client import get_consultant_status, get_job, submit_consult_job


def render_consultant_panel() -> None:
    theme_id = st.session_state.get("selected_theme_id")
    if not theme_id:
        return

    try:
        status = get_consultant_status()
    except Exception:
        return

    if not status.get("enabled"):
        return
    if not (status.get("modes") or {}).get("on_demand", True):
        return

    st.subheader("🎓 ที่ปรึกษาภายนอก (Claude)")
    st.caption(f"โมเดล: {status.get('model', '')} — คำแนะนำจะบันทึกใน Team Memory")

    question = st.text_area(
        "ถามที่ปรึกษา",
        key="consultant_question",
        placeholder="เช่น ทีมควรปรับปรุงการวิเคราะห์ยอดขายอย่างไร",
        height=80,
    )
    if st.button("ปรึกษา Claude", key="consultant_ask_btn", use_container_width=True):
        if not (question or "").strip():
            st.warning("กรุณาพิมพ์คำถาม")
        else:
            try:
                job = submit_consult_job(theme_id, question.strip())
                st.session_state.consult_job_id = job["job_id"]
                st.session_state.consult_advice = None
            except httpx.HTTPStatusError as exc:
                detail = None
                if exc.response.status_code == 409:
                    try:
                        detail = exc.response.json().get("detail")
                    except Exception:
                        detail = None
                if isinstance(detail, dict) and detail.get("job_id"):
                    st.session_state.consult_job_id = detail["job_id"]
                else:
                    st.error(f"ส่งคำปรึกษาไม่สำเร็จ: {exc}")
            except Exception as exc:
                st.error(f"ส่งคำปรึกษาไม่สำเร็จ: {exc}")

    if st.session_state.get("consult_job_id"):
        _poll_consult_job()

    if st.session_state.get("consult_advice"):
        st.markdown(st.session_state.consult_advice)
        st.caption("บันทึกใน Team Memory แล้ว — ทีม Local จะเห็นใน prompt รอบถัดไป")


@st.fragment(run_every=5)
def _poll_consult_job() -> None:
    job_id = st.session_state.get("consult_job_id")
    if not job_id:
        return
    try:
        job = get_job(job_id)
    except Exception:
        st.caption("🎓 ที่ปรึกษา: เช็คสถานะไม่สำเร็จ — จะลองใหม่อัตโนมัติ")
        return

    status = job.get("status")
    if status in ("queued", "running"):
        st.caption("🎓 ที่ปรึกษากำลังคิด... (อาจใช้เวลา 30 วินาที–3 นาที)")
        return

    st.session_state.consult_job_id = None
    if status == "done":
        advice = (job.get("result") or {}).get("advice") or ""
        st.session_state.consult_advice = advice
        st.rerun(scope="app")
    else:
        st.error(f"ที่ปรึกษาล้มเหลว: {job.get('error') or status}")
