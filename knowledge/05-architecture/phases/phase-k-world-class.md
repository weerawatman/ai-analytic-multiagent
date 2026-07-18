# Phase K — World-class Layer: ทีมมืออาชีพที่พัฒนาตัวเอง

<!-- สร้างจาก _TEMPLATE-phase.md ก่อนเขียนโค้ด (Handoff Protocol §4.4 ข้อ 2) -->

> **สถานะ:** เสร็จฝั่งโค้ด + automated tests (2026-07-18) — live success criteria ของ roadmap §10 ค้าง
> **ผู้ดำเนินการ:** AI session (2026-07-18) ตามคำสั่ง owner "ดำเนินการต่อ phase ถัดไปได้เลย" หลัง Phase J push
> **อ้างอิง:** [phase-g-to-k-grand-roadmap.md](phase-g-to-k-grand-roadmap.md) §10 — งานนี้อยู่ใต้ **§4 Delegation Guardrails ทุกข้อ**

---

## Precondition check

| Input | สถานะจริง |
|---|---|
| Phase I (`insight_pipeline`, insights UI, scheduler) | ✅ โค้ดพร้อม; live traffic cold start |
| Phase J (embeddings, SQL patterns, lesson miner, ranker) | ✅ โค้ด + tests; live metrics ค้าง |
| `study` job kind ใน §4.2 | ✅ จองไว้แล้ว — **ไม่ต้อง owner approve** เพื่อเพิ่ม kind |
| Open item O-3 (calendar vs fiscal) | ⏳ ยังไม่ตอบ — digest QoQ/YoY ใช้ **calendar YYYYMM** ตาม snapshot store เดิม และติดป้าย `period_basis=calendar_yyyymm_provisional` |

**ข้อสรุป:** โค้ด + offline tests ครบ; **ห้าม fake** เกณฑ์สำเร็จ live (§10)

---

## Scope

### ทำใน phase นี้ (In)
- [x] `backend/app/services/digest_service.py` — รวม published+useful insights + QoQ/YoY/metric summary → `data/local/briefings/digests/{yyyy-ww}.json`; optional Claude polish ผ่าน redaction/audit เดิม
- [x] `frontend/pages/digest.py` — หน้า digest (ใช้ `st.cache_data`, ไม่มี fragment poll ใหม่ — INV-12)
- [x] API digests + wire scheduler (weekly digest เมื่อ `digest_enabled`; หลัง pipeline เมื่อ `digest_after_pipeline`)
- [x] `data/local/knowledge/curriculum/{role}.json` seed (DA/DS/DE/BA) + `curriculum_store.py` (load/save/pass-rate เป็นตัวเลข)
- [x] Nightly `study` job (`job_runner.start_study_job`) — หยิบ 1–2 ข้อเมื่อเครื่องว่าง → ผลเข้า team memory `study_results` สถานะ **pending_ceo_approve** → match golden question เมื่อมี → อัปเดต pass-rate
- [x] Cross-theme knowledge aggregation — `knowledge_store.aggregate_approved_knowledge` (global + per-theme override) รวม glossary/relationships/targets + sql_lessons
- [x] Eval trend — `eval_service.list_eval_runs` / `eval_trend` + API + ส่วนในหน้า digest
- [x] Config + `.env.example` + README + `scripts/generate_digest.py`
- [x] Tests + gate `K-done.md` + `phase-summaries/phase-k.md`

### ไม่ทำใน phase นี้ (Out)
- **(Optional) sandboxed Python / Phase E** — Docker `execute_python` — deferred; ไม่ implement ในรอบนี้
- ปิด live §10 (digest ≥ 4 สัปดาห์ต่อเนื่อง, pass-rate โตขึ้นจริง, owner ยืนยัน eval trend) — pending gate
- เปลี่ยน period basis เป็น fiscal (รอ O-3)
- เพิ่ม job kind นอกเหนือจาก `study` ที่ล็อกไว้แล้ว (digest ใช้ in-process / script / after-pipeline — ไม่เพิ่ม kind `digest`)
- Prophet / vector DB / Redis / Celery / fragment poll ใหม่ (INV-1, INV-12)

---

## Locked decisions + Canonical names ที่ phase นี้แตะ

| รายการ | ที่มา |
|---|---|
| `digest_service.py` | roadmap §4.2 |
| Job kind `study` | roadmap §4.2 (จองไว้แล้ว) |
| Store: `curriculum/{role}.json`, `briefings/digests/` | roadmap §4.2 |
| Consultant redaction/audit ก่อนส่งภายนอก | phase-3 + roadmap §10 |
| QoQ/YoY provisional บน calendar YYYYMM | snapshot store เดิม; O-3 ยังเปิด |

---

## Definition of Done (กรอกจริงก่อนปิด phase — ห้ามติ๊กล่วงหน้า)

- [x] โค้ดครบตาม Scope In และไม่มีงานนอก scope
- [x] pytest เต็มชุดเขียว (รวม `test_roadmap_conformance.py`) — แนบผลรันจริงท้ายไฟล์
- [x] เกณฑ์สำเร็จของ phase (roadmap §10) ผ่านครบฝั่ง automated/offline; live criteria ค้าง
- [x] สร้าง gate artifact ใน `gates/K-done.md`
- [x] Deviation Log ว่าง **หรือ** ทุกแถวมี owner approve / บันทึกโปร่งใส

---

## Deviation Log

| วันที่ | เรื่องที่เบี่ยง | เหตุผล | Owner approved? |
|---|---|---|---|
| 2026-07-18 | QoQ/YoY ใน digest ใช้ calendar YYYYMM + ป้าย provisional | O-3 ยังไม่ตอบ; ไม่ invent fiscal calendar | ไม่ต้องขอก่อน (reuse convention เดิมของ snapshot store + ติดป้ายชัด) |
| 2026-07-18 | เพิ่ม helper `curriculum_store.py` / `study_service.py` (ไม่อยู่ใน §4.2 service list) | §4.2 ล็อกแค่ path ของ curriculum + job `study` + `digest_service`; helper แยกตามแบบ Phase J | ไม่ต้องขอก่อน (ไม่เปลี่ยนชื่อ canonical) |
| 2026-07-18 | Config keys ใหม่: `digest_enabled`, `study_enabled`, `consultant_polish_digest`, … | ไม่ได้อยู่ใน freeze list เดิมของ §4.2 — เพิ่มแบบ opt-in default off ตาม Phase I/J | ไม่ต้องขอก่อน (เสริม ไม่แทนที่) |
| 2026-07-18 | Weekly digest รัน in-process ใน scheduler (ไม่สร้าง job kind `digest`) | §4.2 job kinds มีแค่ 3 ชนิด; เพิ่ม kind ต้อง owner approve — ใช้ pattern เดียวกับ briefings/script ของ Phase J | ไม่ต้องขอก่อน (หลีกเลี่ยงการขยาย freeze list); study ยังผ่าน job_runner ตาม canonical |

---

## Deferred — Phase E sandbox (optional)

ตาม roadmap §10 และ phase-d locked decision: Docker ใช้ได้**เฉพาะ** `execute_python` สำหรับ DS agent + model persistence — **ยังไม่ implement** จนกว่าจะมี phase doc แยกและ owner สั่งเริ่ม

---

## Verification

```powershell
# รันจาก repo root เสมอ (conftest ต้องการ)
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest backend/tests -q
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest backend/tests/test_roadmap_conformance.py -v
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\generate_digest.py --no-polish
```

---

## ผลเทสต์ / หลักฐานแนบท้าย

**ก่อน Phase K (Phase J summary):** `379 passed`

**หลัง Phase K:** `390 passed in ~88s` (21 warnings จาก joblib/numpy — ไม่ fail)

Conformance: INV-1..INV-9, INV-11 **pass**; `digest_service.py` มีแล้ว → ถูกบังคับโดย INV-9
