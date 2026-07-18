# Phase {X} — {ชื่อ phase}

<!-- คัดลอกไฟล์นี้เป็น phase-{x}-{slug}.md ก่อนเขียนโค้ดบรรทัดแรกของ phase (Handoff Protocol §4.4 ข้อ 2 ใน phase-g-to-k-grand-roadmap.md) -->

> **สถานะ:** {ยังไม่เริ่ม | กำลังทำ | เสร็จ — ระบุสิ่งที่ verified แล้ว vs ยังไม่ verified}
> **ผู้ดำเนินการ:** {ใคร/AI session ไหน ได้รับมอบเมื่อไหร่}
> **อ้างอิง:** [phase-g-to-k-grand-roadmap.md](phase-g-to-k-grand-roadmap.md) §{เลข section ของ phase นี้} — งานนี้อยู่ใต้ **§4 Delegation Guardrails ทุกข้อ**

---

## Scope

### ทำใน phase นี้ (In)
- [ ] {รายการงานตาม roadmap — ระบุไฟล์เป้าหมาย}

### ไม่ทำใน phase นี้ (Out)
- {สิ่งที่อาจถูกเข้าใจผิดว่าอยู่ใน scope — เขียนกันไว้ล่วงหน้า}

---

## Locked decisions + Canonical names ที่ phase นี้แตะ

| รายการ | ที่มา |
|---|---|
| {ชื่อไฟล์/function/table ที่ต้องใช้ตามที่ล็อก} | roadmap §3 / §4.2 |

---

## Definition of Done (กรอกจริงก่อนปิด phase — ห้ามติ๊กล่วงหน้า)

- [ ] โค้ดครบตาม Scope In และไม่มีงานนอก scope
- [ ] pytest เต็มชุดเขียว (รวม `test_roadmap_conformance.py`) — แนบผลรันจริงท้ายไฟล์
- [ ] เกณฑ์สำเร็จของ phase (roadmap §{เลข}) ผ่านครบ พร้อมหลักฐานต่อข้อ
- [ ] สร้าง gate artifact ใน `gates/` แล้ว (ดู `gates/README.md`)
- [ ] Deviation Log ว่าง **หรือ** ทุกแถวมี owner approve

---

## Deviation Log

การเบี่ยงจาก locked decisions / canonical names ใดๆ ต้องบันทึกที่นี่ **และได้รับ owner approve ก่อนลงมือ** — ห้ามทำไปก่อนค่อยบอก

| วันที่ | เรื่องที่เบี่ยง | เหตุผล | Owner approved? |
|---|---|---|---|
| | | | |

---

## Verification

```powershell
# รันจาก repo root เสมอ (conftest ต้องการ)
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_roadmap_conformance.py -v
```
{คำสั่ง/ขั้นตอน verify เฉพาะของ phase นี้ เช่น รัน baseline eval, ตรวจ heartbeat ใน UI}

---

## ผลเทสต์ / หลักฐานแนบท้าย

{วางผล pytest จริง + commit hashes + หลักฐานเกณฑ์สำเร็จ}

---

## Documentation / Handover checklist

ก่อนปิด phase หรือส่งมอบ session ถัดไป — ดู `AGENTS.md` → **Documentation & Handover Contract**

- [ ] Gate artifact ใน `gates/` (หรือ sign-off ที่เกี่ยวข้อง) มีหลักฐานจริง
- [ ] `phase-summaries/phase-{x}.md` อัปเดตตาม `phase-summaries/README.md` (แยก code-complete vs production-verified)
- [ ] Commit hash ใน phase summary **หลัง push** แล้ว
- [ ] `PROJECT_OVERVIEW.md` — วันที่/header commit, §3 readiness, §11 remaining work, §15 handover ตรงความจริง
- [ ] `README.md` — install/run/env ยังถูก (ถ้า phase แตะส่วนนั้น)
- [ ] `docs/diagrams/SYSTEM_DIAGRAMS.md` — อัปเดต diagram ที่เกี่ยวข้องถ้า phase เปลี่ยน architecture/flows (ระบุ section ที่แตะ เช่น §6–§7); ถ้ายังไม่อัปเดต ให้บันทึก diagram debt ใน phase summary
- [ ] ไม่ขัดกันระหว่าง phase doc, gate, overview, summary, diagrams, และ `test_roadmap_conformance.py`
