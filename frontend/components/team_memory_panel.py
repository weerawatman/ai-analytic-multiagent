from urllib.parse import quote

import httpx
import streamlit as st

from components.api_client import get_job, get_json, post_json

ROLE_ORDER = [
    ("data_engineer", "🔧 Data Engineer"),
    ("data_scientist", "🧪 Data Scientist"),
    ("data_analyst", "📈 Data Analyst"),
    ("business_analyst", "💼 Business Analyst"),
]

EVIDENCE_LABELS = {
    "fabric_live": "🟦 Fabric (query จริง)",
    "postgres_live": "🟨 Postgres mirror (query จริง)",
    "disk_cache": "⚪ Cache บนดิสก์ (ยังไม่ได้ query สด)",
}

STATUS_BADGES = {
    "validated": "✅ Validated (รันจริงแล้ว)",
    "not_run": "🟡 Hypothesis (ยังไม่รัน)",
    "failed": "⚠️ รันไม่สำเร็จ",
}


def _clip(value, n: int = 19) -> str:
    """Safe prefix for display — keys may exist with explicit null."""
    return (value or "")[:n]


def _submit_deep_onboarding(theme_id: str, theme_name: str) -> None:
    try:
        job = post_json(
            f"/api/v1/onboarding/{theme_id}/deep-run?theme_name={quote(theme_name)}", {}, timeout=30
        )
        st.session_state.deep_onboarding_job_id = job["job_id"]
        st.toast("เริ่มวิเคราะห์เชิงลึกแล้ว — ทำงานเบื้องหลัง")
    except httpx.HTTPStatusError as exc:
        detail = None
        if exc.response.status_code == 409:
            try:
                detail = exc.response.json().get("detail")
            except Exception:
                detail = None
        if isinstance(detail, dict) and detail.get("job_id"):
            st.session_state.deep_onboarding_job_id = detail["job_id"]
            st.info("มีงานวิเคราะห์เชิงลึกทำงานอยู่แล้ว — ติดตามงานเดิม")
        else:
            st.error(f"เริ่มงานไม่สำเร็จ: {exc.response.status_code}")
    except Exception as exc:
        st.error(f"เริ่มงานไม่สำเร็จ: {exc}")


@st.fragment(run_every=5)
def _poll_deep_onboarding() -> None:
    job_id = st.session_state.get("deep_onboarding_job_id")
    if not job_id:
        return
    try:
        job = get_job(job_id)
    except Exception:
        st.caption("🔬 Deep onboarding: เช็คสถานะไม่สำเร็จ — จะลองใหม่อัตโนมัติ")
        return
    status = job.get("status")
    if status in ("queued", "running"):
        step = job.get("current_step") or "กำลังทำงาน"
        st.caption(f"🔬 Deep onboarding: {step} … (read-only, จำกัดขอบเขต)")
        return
    st.session_state.deep_onboarding_job_id = None
    if status == "done":
        st.toast("Deep onboarding เสร็จแล้ว ✅")
    else:
        st.warning(f"Deep onboarding: {status} — {job.get('error') or ''}")
    st.rerun(scope="app")


def _render_homework(theme_id: str) -> None:
    try:
        hw = get_json(f"/api/v1/onboarding/{theme_id}/homework")
    except Exception:
        st.caption("🔬 ยังไม่มี data homework — กด 'เริ่มวิเคราะห์เชิงลึก' เพื่อให้ทีม profile ข้อมูลจริง")
        return

    evidence = EVIDENCE_LABELS.get(hw.get("evidence_level") or "", hw.get("evidence_level") or "-")
    with st.expander(
        f"🔬 Data Homework — {evidence} · {_clip(hw.get('generated_at'))}", expanded=False
    ):
        roles_map = hw.get("table_roles") or {}
        counts = hw.get("row_counts") or {}
        ranges = hw.get("date_ranges") or {}
        for table, role in list(roles_map.items())[:10]:
            rc = counts.get(table)
            rc_txt = f"{rc:,}" if isinstance(rc, int) else "?"
            rng = ranges.get(table) or {}
            rng_txt = (
                f" · {rng.get('column')}: {rng.get('min')} → {rng.get('max')}" if rng else ""
            )
            st.markdown(f"- `{table}` — **{role}**, {rc_txt} แถว{rng_txt}")

        dq = hw.get("data_quality_issues") or []
        if dq:
            st.markdown("**ประเด็นคุณภาพข้อมูล:**")
            for issue in dq[:6]:
                st.markdown(f"- ⚠️ [{(issue or {}).get('table')}] {(issue or {}).get('detail_th')}")

        role_hw = hw.get("role_homework") or {}
        labels = dict(ROLE_ORDER)
        for role_key, label in ROLE_ORDER:
            section = role_hw.get(role_key) or {}
            if not section:
                continue
            st.markdown(f"**{labels.get(role_key, role_key)} — {section.get('focus_th', '')}**")
            for note in (
                section.get("notes_th")
                or section.get("hypotheses_th")
                or section.get("questions_th")
                or []
            )[:4]:
                st.caption(f"· {note}")
        if hw.get("method_note_th"):
            st.caption(f"ℹ️ {hw['method_note_th']}")


def _render_starter_pack(theme_id: str) -> None:
    try:
        pack = get_json(f"/api/v1/onboarding/{theme_id}/starter-pack")
    except Exception:
        return
    items = pack.get("items") or []
    if not items:
        if pack.get("note_th"):
            st.caption(f"💡 Starter pack: {pack['note_th']}")
        return
    validated = sum(1 for i in items if (i or {}).get("evidence_status") == "validated")
    with st.expander(
        f"💡 Insight Starter Pack — {len(items)} รายการ ({validated} validated)", expanded=False
    ):
        for item in items:
            item = item or {}
            badge = STATUS_BADGES.get(item.get("evidence_status") or "not_run", "🟡")
            st.markdown(f"**{item.get('title_th', '-')}**  \n{badge} · confidence: {item.get('confidence', '-')}")
            st.caption(f"สมมติฐาน: {item.get('hypothesis_th', '-')}")
            st.caption(f"ใช้ตัดสินใจ: {item.get('expected_decision_th', '-')}")
            if item.get("evidence_status") == "validated" and item.get("result_rows"):
                st.dataframe(item["result_rows"], use_container_width=True, height=180)
                st.caption(
                    f"แหล่งข้อมูล: {item.get('executed_source', '-')} · รันเมื่อ {_clip(item.get('executed_at'))}"
                )
            with st.popover("ดู SQL"):
                st.code(item.get("executed_sql") or item.get("sql") or "--", language="sql")
            st.divider()
        st.caption(f"ℹ️ {pack.get('method_note_th', '')}")


def render_team_memory_panel() -> None:
    """Show team onboarding memory per role."""
    theme_id = st.session_state.get("selected_theme_id")
    if not theme_id:
        return

    st.subheader("Team Memory")
    try:
        data = get_json(f"/api/v1/onboarding/{theme_id}")
    except Exception:
        st.caption("ยังไม่มี team onboarding — เลือก theme เพื่อรัน discovery + onboarding")
        _render_role_placeholders()
        return

    status = data.get("status") or "pending"
    icon = {"completed": "✅", "running": "⏳", "failed": "❌"}.get(status, "⏸")
    st.caption(f"{icon} สถานะ: {status} · {_clip(data.get('onboarded_at'))}")

    theme_name = data.get("theme_name") or st.session_state.get("theme_input") or ""
    if st.button("🔬 เริ่มวิเคราะห์เชิงลึก (Deep onboarding)", key="deep_onboarding_btn"):
        _submit_deep_onboarding(theme_id, theme_name)
    if st.session_state.get("deep_onboarding_job_id"):
        _poll_deep_onboarding()
    _render_homework(theme_id)
    _render_starter_pack(theme_id)

    team_summary = data.get("team_summary") or ""
    if team_summary:
        st.markdown(team_summary[:1500])

    recommended = data.get("recommended_tables") or []
    if recommended:
        st.caption("ตารางแนะนำ: " + ", ".join(str(t) for t in recommended[:5]))
    metrics = data.get("key_metrics") or []
    if metrics:
        st.caption("Metrics: " + ", ".join(str(m) for m in metrics[:5]))

    consultant_notes = data.get("consultant_notes") or []
    if consultant_notes:
        with st.expander(f"🎓 คำแนะนำที่ปรึกษา (Claude) — {len(consultant_notes)} รายการ", expanded=True):
            for n in consultant_notes[-3:]:
                at = _clip((n or {}).get("at"))
                note = (n or {}).get("note") or ""
                st.caption(at)
                st.markdown(note[:1500])
                if len(note) > 1500:
                    st.caption("…(ตัดความยาว — ดูเต็มในไฟล์ team memory)")

    roles = data.get("roles") or {}
    for role_key, label in ROLE_ORDER:
        entry = roles.get(role_key) or {}
        summary = entry.get("handoff_summary") or ""
        role_status = entry.get("status") or "pending"
        with st.expander(f"{label} — {role_status}"):
            if summary:
                st.markdown(summary[:1200])
            else:
                st.caption("ยังไม่มี handoff — รอ onboarding หรือ re-run theme")
            notes = entry.get("feedback_notes") or []
            if notes:
                st.caption("CEO feedback:")
                for n in notes[-3:]:
                    st.markdown(f"- [{(n or {}).get('action')}] {(n or {}).get('comment') or ''}")


def _render_role_placeholders() -> None:
    for _, label in ROLE_ORDER:
        with st.expander(f"{label} — รอ onboarding"):
            st.caption("เลือก theme แล้วรอทีมทำการบ้าน (DE → DS → DA → BA)")
