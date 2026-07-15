# PRD — AI Fabric Insight Explorer

**Version:** 1.0  
**Date:** 2026-07-15  
**Status:** Signed off — 2026-07-15 (grill session + human confirm)  
**Derived from:** `knowledge/01-discovery/discovery-brief.md`

---

## Overview

AI Analytics Multi-Agent เป็นระบบ **AI Data Team บนเครื่อง local** ที่เชื่อมต่อ **Microsoft Fabric Data Warehouse (`WH_SAP_PRD`)** เพื่อช่วย Data Engineer สำรวจและวิเคราะห์ insight อย่างละเอียด เก็บผลเป็น **insight candidates** และยกระดับเป็น **Trusted definitions** หลัง validate กับ BA/DA — เพื่อลด definition drift และปรับปรุงวิธีวิเคราะห์ของทีมอย่างต่อเนื่อง

---

## Goals

| # | Goal |
|---|------|
| G1 | เชื่อมต่อ Fabric DW แบบ read-only ด้วย Service Principal |
| G2 | สำรวจข้อมูลในโหมด `Explore` — ละเอียด ถูกต้อง ใช้งานได้จริง (draft) |
| G3 | สะสม insight candidates ใน backlog พร้อม SQL, assumptions, ตัวอย่างตัวเลข |
| G4 | ส่งต่อ BA/DA ด้วยรายงานภาษาไทย + บันทึก feedback กลับระบบ |
| G5 | Promote อย่างน้อย 1 insight เป็น `Trusted` (metric + playbook + example questions) |
| G6 | สแกน schema แล้วเสนอ 3 themes ให้เลือกก่อนเริ่ม Explore ลึก |

---

## Non-Goals (Phase 1)

| # | Non-Goal |
|---|----------|
| NG1 | Multi-user login / BA/DA เข้าระบบ |
| NG2 | Auto-schedule, alerts, dashboards |
| NG3 | ML model training / deployment จริง |
| NG4 | Write-back หรือ auto-modify Fabric DW |
| NG5 | Refactor UI ใหญ่ — ปรับ Streamlit พอใช้เท่านั้น |
| NG6 | PostgreSQL เป็นแหล่งวิเคราะห์ (ตัดออกจาก workflow Phase 1) |
| NG7 | Cloud LLM API — local Ollama เท่านั้น |
| NG8 | เน้นความเร็ว response |

ดูรายละเอียดเพิ่ม: `constraints.md`, `nfr.md`

---

## User Stories

### US-1: Schema Discovery
**As a** Data Engineer  
**I want** the system to scan Fabric schema and propose top 3 themes  
**So that** I can pick a focus area without pre-defined business questions

### US-2: Themed Exploration
**As a** Data Engineer  
**I want** to select a theme and receive AI-generated exploration questions  
**So that** I can discover insight patterns systematically

### US-3: Deep Explore Analysis
**As a** Data Engineer  
**I want** each Explore answer to include SQL, assumptions, sanity checks, and sample rows  
**So that** I can trust the draft enough to discuss with BA/DA

### US-4: Insight Backlog
**As a** Data Engineer  
**I want** promising findings saved as structured backlog items  
**So that** insights are not lost in chat history

### US-5: BA/DA Handoff Report
**As a** Data Engineer  
**I want** to export a Thai report with numbers and open questions  
**So that** I can validate calculation methods with BA/DA offline or in meetings

### US-6: Record BA/DA Feedback
**As a** Data Engineer  
**I want** to record BA/DA responses back into the system  
**So that** validated knowledge can be promoted to Trusted

### US-7: Trusted Promotion (HITL)
**As a** Data Engineer  
**I want** to approve promotion of validated insights into the semantic layer  
**So that** future analysis uses consistent, team-agreed definitions

### US-8: Suggest DW Changes (No Auto-Apply)
**As a** Data Engineer  
**I want** the system to suggest DW improvements (views, definitions)  
**So that** I can decide and implement changes myself — the system never writes to Fabric

---

## Functional Requirements

### FR-1: Fabric Connection
- FR-1.1 Connect to Fabric DW using Service Principal (Entra ID)
- FR-1.2 Environment variables: `FABRIC_SERVER`, `FABRIC_DATABASE`, `FABRIC_TENANT_ID`, `FABRIC_CLIENT_ID`, `FABRIC_CLIENT_SECRET`
- FR-1.3 Connection health check endpoint or UI indicator

### FR-2: Read-Only SQL Guard
- FR-2.1 Allow only SELECT (and read-safe constructs e.g. CTEs, subqueries)
- FR-2.2 Block DDL, DML, EXEC, and other write/admin statements
- FR-2.3 Log all executed SQL with timestamp and mode (`Explore` / `Trusted`)

### FR-3: Explore Mode
- FR-3.1 User selects or confirms a theme
- FR-3.2 AI generates exploration sub-questions within theme
- FR-3.3 All Explore outputs labeled **draft / รอ validate**
- FR-3.4 Heavy quality bar per candidate (see § Quality Bar)

### FR-4: Trusted Mode
- FR-4.1 Only uses definitions marked Trusted in semantic layer
- FR-4.2 Trusted SQL references approved metrics/filters/grain
- FR-4.3 Promotion requires explicit human approval (HITL)

### FR-5: Multi-Agent Orchestration
- FR-5.1 Retain 3 agents: Data Engineer, Data Analyst, Data Scientist
- FR-5.2 Data Engineer: schema, semantic layer, HITL proposals
- FR-5.3 Data Analyst: SQL generation, pattern analysis
- FR-5.4 Data Scientist: alternative analytical angles, challenge assumptions in Explore
- FR-5.5 LangGraph router + approval interrupt for semantic changes

### FR-6: Insight Backlog
- FR-6.1 Store candidates in JSON under `data/local/backlog/`
- FR-6.2 Fields: id, theme, question, answer_summary, sql, assumptions, confidence, sample_data_ref, status, created_at, ba_da_feedback
- FR-6.3 Status values: `new`, `discussing`, `validated`, `rejected`, `promoted`

### FR-7: Chat History
- FR-7.1 Persist conversation sessions in SQLite (`data/local/app.db`)
- FR-7.2 Link sessions to backlog items where applicable

### FR-8: Semantic / Trusted Layer
- FR-8.1 JSON semantic layer under `data/local/semantic/` (promoted) + templates under `data/templates/`
- FR-8.2 Trusted entry includes: metric name, business definition (TH), SQL reference, grain, filters, validated assumptions, short playbook, example questions

### FR-9: Export & Feedback
- FR-9.1 Generate Markdown report (Thai) per backlog item
- FR-9.2 Include sample tables/aggregations
- FR-9.3 UI field to record BA/DA feedback and link to promotion flow

### FR-10: Schema Theme Proposal
- FR-10.1 On first run (or explicit action), scan INFORMATION_SCHEMA / sys tables
- FR-10.2 Propose 3 themes ranked by: data richness, business relevance signals, exploration potential
- FR-10.3 Present themes in Thai with suggested starter questions

---

## Quality Bar (Explore Output — Level D)

Every insight candidate saved to backlog **must** include:

| # | Requirement |
|---|-------------|
| Q1 | Executable SQL against Fabric |
| Q2 | Stated assumptions (grain, filters, time range, joins) |
| Q3 | Confidence level + known unknowns |
| Q4 | At least one alternative SQL or sanity check |
| Q5 | Sample rows or sub-aggregations as evidence |
| Q6 | List of questions to ask BA/DA for validation |

---

## Constraints

See `constraints.md`.

## Non-Functional Requirements

See `nfr.md`.

## Acceptance Criteria

See `acceptance-criteria/phase-1-core-loop.md`.

---

## Open Questions

| # | Question | Owner | Status |
|---|----------|-------|--------|
| OQ-1 | Which ~14B Ollama model to standardize on first? | DE | Open |
| OQ-2 | Exact Fabric SQL driver (pyodbc vs ODBC 18 + Entra SP)? | DE/Build | Open |
| OQ-3 | First theme selection after schema scan | DE | Pending scan |
| OQ-4 | BA/DA availability timeline for validation loop | DE | Open |

---

## Phase 1 Definition of Done

- [ ] Fabric connected read-only with SP
- [ ] Schema scan proposes 3 themes; user picks 1
- [ ] ≥1 insight candidate passes Quality Bar D and enters backlog
- [ ] Export report generated in Thai
- [ ] BA/DA feedback recorded (even if placeholder from owner acting as validator)
- [ ] ≥1 item promoted to Trusted with playbook + example questions
- [ ] No PostgreSQL dependency in runtime path
- [ ] `data/local/` gitignored; templates committed

---

## Human Gate

- [x] PRD reviewed and signed off by project owner
- [x] Scope and non-goals agreed
- [x] Acceptance criteria reviewed

**Sign-off:** Data Engineer (owner) — 2026-07-15
