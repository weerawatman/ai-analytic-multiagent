# Defect handoff — DEF-001

> **วันที่:** 2026-07-18
> **From run:** `20260718-191418-3b7689`
> **Fixed in run:** `20260718-203027-487673`
> **Scenario:** SCN-ENV-002 (and SCN-LLM-001 risk for Explore)
> **Severity:** high
> **Category:** llm

## Summary (Thai, one paragraph)

โมเดลที่ตั้งใน `.env` (`qwen2.5-coder:7b`) โหลดไม่ได้ตอน inference smoke — Ollama คืน HTTP 500 ประเภท out-of-memory ขณะ allocate buffer บน CPU แม้ `/api/tags` และบริการ Backend/Frontend จะปกติ มี RAM ว่างประมาณ 7–8 GB จาก ~28 GB รวม ซึ่งไม่พอสำหรับ 7b หลัง overhead โมเดลสำรอง `qwen2.5-coder:1.5b` generate ได้สำเร็จ แต่ยังต่ำกว่าเป้าคุณภาพ Phase 1 (~14B)

## Repro

1. Preconditions: Ollama reachable; Backend/Frontend healthy; `OLLAMA_MODEL` = `qwen2.5-coder:7b`
2. Command: `.\scripts\run-readiness-check.ps1 -Level 1` หรือ POST `/api/generate` ด้วย `num_predict=1`
3. Observed: SCN-ENV-002 fail; exception type `WebException`; error class = out-of-memory during model startup
4. Expected: generate smoke สำเร็จโดยไม่ OOM

## Evidence (pointers only)

- Raw run dir (fail): `data/local/qa/loop-engineering/runs/20260718-191418-3b7689/`
- Raw run dir (fix): `data/local/qa/loop-engineering/runs/20260718-203027-487673/`
- Log hint: Ollama generate response body (exception type / OOM class only — ไม่ใส่ dump เต็มในรายงาน)
- Related: SCN-LLM-001 pattern (agents ⚠️ ทั้งชุดถ้า weights โหลดไม่ได้)
- Repair attempted: unload models + retry 7b — ยัง OOM (round 1/3)
- Repair round 2: pull + generate smoke `qwen2.5-coder:3b` → OK; set `OLLAMA_MODEL=qwen2.5-coder:3b`; restart backend; L0+L1 green

## Suggested owner

| Category | Delegate |
|----------|----------|
| llm / Ollama | main agent (config) + owner (RAM / model choice) |

## Allowed fix scope

- ปลดหน่วยความจำเครื่อง / ปิดแอปที่ใช้ RAM หนัก แล้ว retry 7b หรือ 14b
- หรือเปลี่ยน `OLLAMA_MODEL` ชั่วคราวเป็นโมเดลที่โหลดได้ (เช่น `qwen2.5-coder:3b` / `1.5b`) — ยอมรับคุณภาพ Explore ต่ำลง
- Do **not** weaken conformance tests
- Do **not** commit/push without user request
- Max repair rounds remaining: 0 (หลัง round 2 ที่ปิด defect)

## Resolution

- [x] Fixed — via smaller model: `OLLAMA_MODEL=qwen2.5-coder:3b` (largest qwen2.5-coder that loads without OOM after 7b failed; generate smoke OK; 1.5b kept as fallback)
- [ ] Won't fix (reason)
- [ ] Needs human gate (owner: free RAM or accept smaller model)
- [x] Regression re-run: **pass** — `20260718-203027-487673` (SCN-ENV-002 pass; 390 pytest; 11 conformance)

**สถานะ:** ปิดด้วยการถ่ายลง 3b ตามคำสั่ง owner (semi-auto). คุณภาพ Explore ต่ำกว่าเป้า ~14B/7b — ยังไม่ production-verified; L2 SCN-CHAT-001 partial/not-run (wall-time cap ~10–12 นาทีบน CPU)
