# Acceptance Criteria — Phase 1 Core Loop

**Feature:** End-to-end Explore → Backlog → BA/DA Feedback → Trusted  
**PRD reference:** `knowledge/03-prd/prd.md`

---

## AC-1: Fabric Read-Only Connection

**Given** valid Service Principal credentials in `.env`  
**When** the application starts and runs a health check  
**Then** it connects to `WH_SAP_PRD` successfully  
**And** a test `SELECT 1` (or equivalent) succeeds  
**And** an attempted `INSERT`/`UPDATE`/`DELETE` is blocked by the SQL guard

### Edge cases
- Invalid/expired client secret → clear Thai error message
- Network timeout → retry suggestion shown
- SP lacks permission on a table → error logged with table name

---

## AC-2: Schema Scan & Theme Proposal

**Given** a successful Fabric connection  
**When** the user triggers schema discovery (or first-run wizard)  
**Then** the system scans available schemas/tables  
**And** proposes exactly 3 themes in Thai  
**And** each theme includes: name, rationale, table count estimate, 2–3 starter questions

---

## AC-3: Themed Explore Session

**Given** the user selects one proposed theme  
**When** Explore mode is active  
**Then** the system generates exploration sub-questions within that theme  
**And** each answer is labeled **Draft / รอ validate กับ BA/DA**

---

## AC-4: Quality Bar D — Backlog Save

**Given** an Explore analysis completes  
**When** the user saves it as an insight candidate  
**Then** the backlog item contains all of:
- Question (TH)
- Answer summary (TH)
- Executable SQL
- Assumptions list
- Confidence + unknowns
- Alternative SQL or sanity check
- Sample rows or sub-aggregation reference
- Questions for BA/DA

**And** the item is stored in `data/local/backlog/` as JSON

---

## AC-5: Export Handoff Report

**Given** a backlog item exists  
**When** the user exports a handoff report  
**Then** a Markdown file is generated in Thai  
**And** includes SQL, assumptions, sample data, and BA/DA discussion prompts  
**And** file is saved under `data/local/exports/`

---

## AC-6: BA/DA Feedback Capture

**Given** a backlog item with status `new` or `discussing`  
**When** the user records BA/DA feedback  
**Then** feedback is appended to the backlog item with timestamp  
**And** status can be updated to `validated`, `rejected`, or remain `discussing`

---

## AC-7: Trusted Promotion (HITL)

**Given** a backlog item with status `validated`  
**When** the user requests promotion to Trusted  
**Then** the system shows a preview of the semantic entry (metric, assumptions, playbook, example questions)  
**And** promotion only completes after explicit approval  
**And** the entry is written to `data/local/semantic/trusted.json` (or equivalent)

---

## AC-8: Trusted Mode Query

**Given** at least one Trusted definition exists  
**When** the user switches to Trusted mode and asks a related question  
**Then** the system references Trusted definitions in its reasoning  
**And** does not contradict validated assumptions without flagging conflict

---

## AC-9: No PostgreSQL Runtime Dependency

**Given** Phase 1 deployment  
**When** the application runs without PostgreSQL container  
**Then** chat, backlog, and semantic features work via local JSON + SQLite  
**And** no analytics queries are routed to PostgreSQL

---

## AC-10: Data Isolation

**Given** git repository state  
**When** `git status` is checked after normal usage  
**Then** `data/local/` contents are not tracked  
**And** `data/templates/` may be tracked without business data

---

## Phase 1 Done Checklist

- [ ] AC-1 through AC-10 pass
- [ ] One complete theme cycle documented in backlog
- [ ] ≥1 Trusted entry with playbook + example questions
- [ ] Owner sign-off on `knowledge/07-testing/sign-off.md` (future)
