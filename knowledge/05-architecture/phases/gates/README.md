# Phase Gates — หลักฐานจบ phase (เก็บใน git เพราะ `data/local/` ไม่อยู่ใน git)

โฟลเดอร์นี้คือ audit trail ของ roadmap G→K ([phase-g-to-k-grand-roadmap.md](../phase-g-to-k-grand-roadmap.md) §4.3) — ผู้ตรวจดูไฟล์ที่นี่ + รัน pytest ก็รู้สถานะจริงโดยไม่ต้องเชื่อคำรายงานของผู้ทำ

## กติกา

1. **ใครสร้าง:** AI/ผู้ดำเนินการของ phase นั้น สร้างเมื่อเกณฑ์สำเร็จผ่านครบจริงเท่านั้น (ห้ามสร้างล่วงหน้า)
2. **เนื้อหาขั้นต่ำทุกไฟล์:** วันที่, commit hash ของงาน, checklist เกณฑ์สำเร็จของ phase (จาก roadmap §6–§10) พร้อมหลักฐานจริงต่อข้อ, ผล pytest แนบ
3. **ไฟล์พิเศษ `G3-baseline-recorded.md`:** ต้องมี **ก่อน** `backend/app/analytics/` ถูกสร้าง (INV-11 — conformance test บังคับ) — เนื้อหา: วันที่รัน baseline, จำนวน golden questions, `accuracy_pct`, `sql_success_rate`, `median_latency_s`, source ที่ใช้ (fabric/postgres), commit hash — คัดลอกผลจาก `data/local/eval/results/` มาเก็บไว้ที่นี่เพราะ data/local ไม่เข้า git
4. **ห้ามแก้ gate เก่าย้อนหลัง** — ถ้าผลเปลี่ยน ให้เพิ่มไฟล์ใหม่ (เช่น `G3-baseline-recorded-v2.md`) พร้อมเหตุผล

## ไฟล์ที่คาดหวัง (ตามลำดับเวลา)

| ไฟล์ | จังหวะ |
|---|---|
| `G3-baseline-recorded.md` | จบ G3, ก่อนเริ่ม Phase H (บังคับโดย INV-11) |
| `G-done.md` | จบ Phase G |
| `H-done.md` | จบ Phase H (ต้องแนบผล validation จับ event อดีต ≥ 3 กรณี) |
| `I-done.md` | จบ Phase I (ต้องแนบสถิติ insights/สัปดาห์ + useful rate เดือนแรก) |
| `J-done.md` | จบ Phase J (ต้องแนบ accuracy เทียบ baseline + ranker AUC) |
| `K-done.md` | จบ Phase K |
