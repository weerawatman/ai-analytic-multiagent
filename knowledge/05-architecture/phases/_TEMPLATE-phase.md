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
