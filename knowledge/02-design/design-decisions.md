# Design Decisions — Phase 1

**Date:** 2026-07-15  
**Status:** Approved for PRD  
**Derived from:** Grill session, discovery brief, user journeys

---

## DD-01: Dual Mode (Explore / Trusted)

**Decision:** แยกโหมดชัดเจน — ไม่มี "โหมดเดียว"  
**Rationale:** Owner ต้องการ explore กว้าง แต่ไม่หลอกตัวเองว่า insight ถูกต้องก่อน validate BA/DA  
**Impact:** UI ต้องมี toggle + badge; API รับ `mode` parameter

---

## DD-02: Theme-First Exploration

**Decision:** เลือก theme ก่อน → AI แตกคำถamodel  
**Rationale:** ไม่มี starter questions; ป้องกันคำถามกระจัด  
**Impact:** Schema scan เป็น first-run flow; theme เก็บใน session state

---

## DD-03: Quality Over Speed in Output Layout

**Decision:** แสดง SQL + assumptions + sample + sanity check ใน chat response เสมอ (Explore)  
**Rationale:** Priority สูงสุดคือเนื้อหาเชิงลึก ไม่ใช่ UX สวย  
**Impact:** Chat bubble ยาว; ใช้ expander สำหรับ SQL/sample

---

## DD-04: Thai Reports, English Technical

**Decision:** UI/รายงานไทย; SQL/schema/metric_key อังกฤษ  
**Rationale:** คุย BA/DA ไทย; ลด definition drift จาก translation  
**Impact:** Template fields แยก `*_th` vs English keys

---

## DD-05: Sidebar Backlog (Not Separate App)

**Decision:** Backlog อยู่ sidebar เดียวกับ chat — ไม่ทำหน้าใหม่  
**Rationale:** Non-goal = no big UI refactor; solo user  
**Impact:** Streamlit sidebar + expander for detail

---

## DD-06: HITL for All Promotions

**Decision:** ทุก Trusted promotion ต้อง preview + approve  
**Rationale:** ปัญหาหลักคือ definition drift — ห้าม auto-promote  
**Impact:** Reuse existing approval panel pattern; extend for Trusted

---

## DD-07: BA/DA Feedback In-System, Interaction Out-of-System

**Decision:** BA/DA ไม่ login; DE บันทึก feedback เองหลังคุย  
**Rationale:** Phase 1 solo user; ลด complexity  
**Impact:** Textarea + timestamp on backlog item; no notification

---

## DD-08: Export as Markdown File

**Decision:** Export เป็น `.md` ใน `data/local/exports/`  
**Rationale:** ส่งต่อ meeting/email ได้; diff ได้; ไม่ต้อง PDF engine  
**Impact:** Report generator service in backend

---

## DD-09: Progress Visibility for Long Runs

**Decision:** แสดง spinner + ข้อความ agent ที่ทำงาน  
**Rationale:** Local 14B–32B ช้า — user ต้องรู้ว่าระบบไม่ค้าง  
**Impact:** Streamlit status callbacks or polling

---

## DD-10: No Auth UI

**Decision:** localhost ไม่มี login  
**Rationale:** Solo Phase 1 on personal machine  
**Impact:** Phase 2 ต้องออกแบบ auth แยก

---

## Rejected Alternatives

| Alternative | Why rejected |
|-------------|--------------|
| Single chat mode (no Explore/Trusted) | ขัดกับ draft vs validated requirement |
| Power BI embed for visuals | Out of scope; focus text/SQL insight |
| Real-time collaboration | Phase 2+ |
| Auto-promote after N runs | ขัด HITL principle |

---

## Traceability

| Decision | PRD | Journey |
|----------|-----|---------|
| DD-01 | FR-3, FR-4 | `02-explore-to-trusted-loop.md` |
| DD-02 | FR-10 | `01-first-run-schema-discovery.md` |
| DD-03 | Quality Bar D | `02-explore-to-trusted-loop.md` |
| DD-05 | NG5 | `wireframes/phase-1-streamlit-layout.md` |
