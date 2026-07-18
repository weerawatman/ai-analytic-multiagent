"""Board digest + eval trend (Phase K) — Streamlit multipage.

Uses ``st.cache_data(ttl=30)`` per INV-12 — no new fragment poll.
"""

from __future__ import annotations

import streamlit as st

from components.api_client import get_json, post_json

st.title("📋 Board Digest")
st.caption(
    "สรุปรายสัปดาห์สำหรับผู้บริหาร — insights ที่มีประโยชน์ + QoQ/YoY "
    "(calendar YYYYMM ชั่วคราว จนกว่า O-3 จะล็อก)"
)

SOURCE_LABELS = {
    "fabric": "🟦 Fabric",
    "postgres": "🟨 Postgres",
    "offline": "⚪ Offline",
}


@st.cache_data(ttl=30)
def _fetch_list() -> list[dict]:
    try:
        data = get_json("/api/v1/digests?limit=12")
        return data.get("items", [])
    except Exception:
        return []


@st.cache_data(ttl=30)
def _fetch_digest(week_key: str | None) -> dict:
    try:
        if week_key:
            return get_json(f"/api/v1/digests/{week_key}")
        return get_json("/api/v1/digests/current")
    except Exception:
        return {}


@st.cache_data(ttl=30)
def _fetch_curriculum() -> dict:
    try:
        return get_json("/api/v1/curriculum")
    except Exception:
        return {}


@st.cache_data(ttl=30)
def _fetch_eval_trend() -> dict:
    try:
        return get_json("/api/v1/eval/trend?limit=30")
    except Exception:
        return {}


col1, col2 = st.columns([3, 1])
with col2:
    if st.button("🔄 สร้าง digest สัปดาห์นี้", use_container_width=True):
        try:
            doc = post_json("/api/v1/digests/generate", {})
            st.success(f"สร้างแล้ว: {doc.get('week_key')}")
            _fetch_list.clear()
            _fetch_digest.clear()
        except Exception as exc:
            st.error(f"สร้างไม่สำเร็จ: {exc}")

digest_list = _fetch_list()
week_options = [d.get("week_key") for d in digest_list if d.get("week_key")]
selected = None
if week_options:
    selected = st.selectbox("เลือกสัปดาห์ (ISO)", week_options, index=0)
else:
    st.info("ยังไม่มี digest — กดสร้าง หรือรอรอบอาทิตย์ (DIGEST_ENABLED)")

digest = _fetch_digest(selected) if selected else {}
if digest:
    st.subheader(f"สัปดาห์ {digest.get('week_key')}")
    st.caption(
        f"สร้างเมื่อ {digest.get('generated_at')} · "
        f"period_basis={digest.get('period_basis')} · "
        f"insights มีประโยชน์ {digest.get('counts', {}).get('useful_insights', 0)}"
    )
    if digest.get("polish_th"):
        st.markdown("### สรุปขัดเกลา")
        st.write(digest["polish_th"])

    st.markdown("### Insights ที่ useful")
    insights = digest.get("insights") or []
    if not insights:
        st.caption("ยังไม่มี insight ที่ published+useful ในรอบนี้")
    for item in insights:
        src = SOURCE_LABELS.get(item.get("source") or "", "")
        with st.container(border=True):
            st.markdown(
                f"**{item.get('metric_key')} · {item.get('period')}** {src}"
            )
            st.write(item.get("narrative_th") or "_(ไม่มี narrative)_")

    st.markdown("### Metric summary / QoQ / YoY")
    rows = digest.get("metric_summaries") or []
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.caption("ยังไม่มี snapshot — รัน snapshot_refresh ก่อน")

st.divider()
st.subheader("📈 Eval trend (ฉลาดขึ้นจริง?)")
trend = _fetch_eval_trend()
runs = trend.get("runs") or []
if runs:
    chart_rows = [
        {
            "finished_at": r.get("finished_at") or r.get("run_id"),
            "accuracy_pct": r.get("accuracy_pct") or 0,
            "sql_success_rate": r.get("sql_success_rate") or 0,
        }
        for r in runs
    ]
    st.line_chart(chart_rows, x="finished_at", y=["accuracy_pct", "sql_success_rate"])
    st.caption(
        f"รอบแรก accuracy={trend.get('first_accuracy_pct')}% · "
        f"ล่าสุด={trend.get('latest_accuracy_pct')}% · รวม {trend.get('run_count')} รอบ"
    )
else:
    st.caption("ยังไม่มีผล eval ใน data/local/eval/results/")

st.divider()
st.subheader("🎓 Curriculum pass-rate")
cur = _fetch_curriculum()
roles = cur.get("roles") or {}
if roles:
    st.metric("Overall pass-rate", f"{cur.get('overall_pass_rate_pct', 0)}%")
    st.dataframe(
        [
            {
                "role": role,
                "attempted": stats.get("attempted"),
                "passed": stats.get("passed"),
                "pass_rate_pct": stats.get("pass_rate_pct"),
                "questions": stats.get("question_count"),
            }
            for role, stats in roles.items()
        ],
        use_container_width=True,
    )
    if st.button("เริ่ม study job (1–2 ข้อ/role)"):
        try:
            job = post_json("/api/v1/study/run", {"theme_id": "sales"})
            st.success(f"ส่ง study job แล้ว: {job.get('job_id', '')[:8]}")
        except Exception as exc:
            st.error(f"ส่งงานไม่สำเร็จ: {exc}")
else:
    st.caption("ยังไม่มี curriculum — จะ seed อัตโนมัติเมื่อเรียก API")
