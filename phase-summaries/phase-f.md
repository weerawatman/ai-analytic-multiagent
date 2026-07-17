# Phase F — Postgres WH_Silver Fallback (สรุปย่อ)

**วันที่:** ~2026-07  
**เอกสารหลัก:** [phase-f-postgres-fallback.md](../knowledge/05-architecture/phases/phase-f-postgres-fallback.md)

## สิ่งที่ทำแล้ว

- Auto-fallback Fabric → Postgres เมื่อ Fabric unreachable/paused (ไม่เงียบ — มี provenance ทุกผลลัพธ์)
- CAST guidance, numeric overlay (CE1SATG), parity tooling, `/fabric/sources`, UI แสดง fallback state
- Automated tests offline ผ่านตามที่ phase doc บันทึก

## งานคงเหลือ / เกตที่ค้าง

- DBA/ทีมข้อมูลปิด checklist D-1/D-2 ใน phase doc
- รัน `scripts/verify_pg_parity.py` กับ live DB ซ้ำ
- Live E2E ผ่าน LLM จริง — ยังไม่ถือ production-verified

## commits ที่เกี่ยวข้อง

- `8e34d28` — `feat(phase-f): postgres fallback provenance, CAST guidance, parity tooling, CE1SATG overlay`
