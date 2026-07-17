# AI Fabric Insight Explorer

Local **AI Data Team** (LangGraph multi-agent) for **Microsoft Fabric Data Warehouse** — Explore draft insights, backlog handoff to BA/DA, and promote **Trusted** definitions after human approval.

**Phase 1 runtime:** Native Windows · FastAPI + Streamlit + Ollama · Fabric read-only (Service Principal) · local JSON + SQLite (no PostgreSQL in the main path)

---

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Python 3.11+** | venv created automatically by run scripts |
| **Microsoft ODBC Driver 18 for SQL Server** | `winget install Microsoft.msodbcsql.18` |
| **Ollama** | Local or LAN server; recommended model: `qwen2.5-coder:14b` |
| **Fabric Service Principal** | Entra ID app + secret **Value**; SP added to target Fabric workspace |
| **Git** | Clone this repo |

---

## First-time setup

1. **Clone and enter the project**
   ```powershell
   git clone https://github.com/weerawatman/ai-analytic-multiagent.git
   cd ai-analytic-multiagent
   ```

2. **Create `.env` from template**
   ```powershell
   copy .env.example .env
   ```
   Edit `.env` and fill in at minimum:

   | Variable | Where to get it |
   |----------|-----------------|
   | `FABRIC_SERVER` | Fabric Portal → open your Warehouse → **Copy SQL connection string** → `Server=` |
   | `FABRIC_DATABASE` | Same string → `Initial Catalog=` (e.g. `WH_Silver`) |
   | `FABRIC_TENANT_ID` | Entra ID → Overview |
   | `FABRIC_CLIENT_ID` | App registration → Application (client) ID |
   | `FABRIC_CLIENT_SECRET` | App registration → Certificates & secrets → **Value** (not Secret ID) |
   | `OLLAMA_BASE_URL` | e.g. `http://127.0.0.1:11434` or your LAN Ollama host |
   | `OLLAMA_MODEL` | e.g. `qwen2.5-coder:14b` |
   | `BACKEND_URL` | Keep `http://127.0.0.1:8000` for native run |

   **Important:** `FABRIC_SERVER` + `FABRIC_DATABASE` must come from the **same** Warehouse connection string. The display name in Fabric UI (e.g. WH_Silver) may differ from warehouses on other workspaces.

   Optional tuning (defaults in `.env.example` are fine):

   | Variable | Purpose |
   |----------|---------|
   | `CHAT_JOB_MAX_SECONDS` | Wall-clock cap for the chat agent graph (pipeline + SQL retries), default 1200s. The consultant review step is bounded separately by `CONSULTANT_TIMEOUT` + 30s. |
   | `ONBOARDING_JOB_MAX_SECONDS` | Wall-clock cap for a whole onboarding job (DE→DA→DS→BA + coach), default 3600s. |
   | `FRONTEND_HTTP_TIMEOUT` | Streamlit → backend HTTP timeout in seconds (default 600). Renamed from `COMPOSE_HTTP_TIMEOUT`; the old name is still honored as a fallback. |

3. **Grant SP access in Fabric**
   - Workspace → **Manage access** → add your Service Principal (e.g. Viewer or higher)
   - Ensure the SP can read the target Warehouse

4. **Pull Ollama models** (on the machine running Ollama)
   ```powershell
   .\scripts\setup-ollama-models.ps1 -BaseUrl http://127.0.0.1:11434 -Profile default
   ```
   Use `-BaseUrl` if Ollama runs on another host (e.g. `http://172.16.6.160:11434`).

5. **Install dependencies** (optional — run scripts also do this)
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r backend\requirements.txt
   pip install -r frontend\requirements.txt
   ```

---

## Run (every time you start work)

Open **two terminals** from the project root:

**Terminal 1 — Backend**
```powershell
.\scripts\run-backend.ps1        # ปกติ: ไม่มี hot-reload — งานที่กำลังรันไม่ถูกฆ่าเมื่อไฟล์เปลี่ยน
.\scripts\run-backend.ps1 -Dev   # ตอนพัฒนา: hot-reload (การ save ไฟล์ backend จะฆ่างานที่กำลังรัน)
```

**Terminal 2 — Frontend**
```powershell
.\scripts\run-frontend.ps1
```

| Service | URL |
|---------|-----|
| **Streamlit UI** | http://127.0.0.1:8501 |
| **FastAPI docs** | http://127.0.0.1:8000/docs |
| **Fabric health** | http://127.0.0.1:8000/api/v1/fabric/health |

In the UI sidebar, check Fabric status. If capacity is paused you can still Explore
from cached discovery / themes, use Consultant, and Team Memory — live SQL is skipped
until Fabric is reachable again (or set `FABRIC_SQL_ENABLED=false` to force offline).

### Fabric pause / offline Explore

Works without a live warehouse when these exist under `data/local/`:

- `themes/cached_themes.json` — list themes in the sidebar
- `knowledge/themes/{theme_id}/discovery.json` — schema context for agents
- optional: `team_memory/{theme_id}.json`, `knowledge/sql_reference/`, glossary

Still needs: **Ollama** for the local AI team (`OLLAMA_BASE_URL`, default model ~7B–14B depending on RAM), and (optional) **Anthropic** for Consultant.

If LAN Ollama is unreachable, point `.env` to local:

```
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5-coder:7b
```

Re-verify Phase 3 remaining checks:

```powershell
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\verify_phase3_remaining.py
```

Does **not** work offline: Schema scan, fresh Discovery against Fabric, executing SQL for real row samples.

---

## Typical workflow (Phase 2)

1. **Scan schema** → pick a theme (sidebar)
2. **Discovery runs automatically** — team profiles columns, samples, relationships
3. **Team Onboarding (Phase 2.5)** — DE → DS → DA → BA do homework; results in **Team Memory** panel (~20–40 min on first run)
4. **CEO Briefing** (main panel) — review 4-role briefs; approve/reject/comment (feedback routes to glossary/targets/relationships)
5. **Knowledge panel** — add glossary (e.g. field definitions), targets, join mappings
6. **(Optional) SAP Table Descriptions** — import DD02T CSV once (see below)
7. **Explore mode** → ask questions → collaborative pipeline (DE → Analyst → Scientist → BA) using team memory baseline
8. Save **Insight Candidate** → export handoff → BA/DA feedback → **Promote to Trusted**
9. **Trusted mode** → query using approved definitions

Phase 1 backlog/promotion flow still applies; Phase 2 adds discovery, knowledge, and CEO loop. Phase 2.5 adds proactive team onboarding + feedback routing.

### SAP Table Descriptions (DD02T export)

Import your SAP table metadata CSV once so agents know what each table means (e.g. `VBRK` = Billing Document Header).

**CSV format:** `TABNAME,DDLANGUAGE,DDTEXT` (English rows use `DDLANGUAGE=E`)

**Option A — script (recommended for large files ~800k rows):**

```powershell
.\scripts\import-sap-table-descriptions.ps1 -CsvPath "$env:USERPROFILE\Downloads\SAP_Table_Description.csv"
```

**Option B — UI:** Sidebar → Knowledge → **SAP Tables** → set path → **นำเข้า**

**Option C — API:**

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/knowledge/sap-tables/import `
  -H "Content-Type: application/json" `
  -d '{\"csv_path\": \"C:\\Users\\you\\Downloads\\SAP_Table_Description.csv\", \"language\": \"E\"}'
```

Data is stored in `data/local/knowledge/sap_tables.db` (SQLite, gitignored). After import, when you select a theme and run discovery, the **Schema Context Pack** includes matched SAP descriptions for theme tables (e.g. `VBRK_All_Cleaned` → `VBRK`).

### Phase 2.5 — Team Onboarding

After discovery, the system runs a **team onboarding graph** (DE → DS → DA → BA) before you ask questions. Output is stored in `data/local/team_memory/{theme_id}.json` and injected into all agent prompts.

**API:**

```powershell
# Run manually (also triggered when selecting a theme in UI)
curl -X POST "http://127.0.0.1:8000/api/v1/onboarding/sales/run?theme_name=ยอดขายและลูกค้า"

# View team memory
curl http://127.0.0.1:8000/api/v1/onboarding/sales
```

**CEO feedback routing:** Comments on briefs update role-owned stores — DE → relationships, DA → glossary, BA → targets (draft until approved in Knowledge panel).

See `knowledge/05-architecture/phases/phase-2.5.md` for full design.

### WH_Silver T-SQL Reference (transform / view DDL)

Store cleaned-table SQL from your WH_Silver repo locally so agents can reference ELT logic without querying Fabric DDL.

| Location | Purpose |
|----------|---------|
| `data/templates/sql_reference/` | Committed templates + README (Thai) — mirrors `WH_Silver/SAPHANADB/` layout |
| `data/local/knowledge/sql_reference/` | Runtime files (gitignored); auto-created on backend start |
| `.../SAPHANADB/Tables/` | Table DDL / cleaned definitions (e.g. `VBRK_All_Cleaned.sql`) |
| `.../SAPHANADB/StoredProcedures/` | Load procedures (e.g. `usp_Load_VBRK_Month.sql`) |
| `.../_manifest.json` | Index of SQL files (auto-regenerated by sync script) |

**Quick start:** Sync from your WH_Silver SQL folder:

```powershell
.\scripts\sync-wh-silver-sql.ps1 -SourcePath "C:\SAT_Fabric_Knowledge\01_SQL\WH_Silver"
```

See `data/templates/sql_reference/README.md` for the full workflow. Loader integration is planned for a later sprint.

---

## Typical workflow (Phase 1 — reference)

1. **Scan schema** → pick a theme (sidebar)
2. **Explore mode** → ask questions → save **Insight Candidate**
3. **Export** Thai Markdown handoff report
4. Record **BA/DA feedback** → status `validated`
5. **Promote to Trusted** → HITL approve
6. **Trusted mode** → query using approved definitions

---

## Validation & tests

```powershell
# Unit/integration tests
$env:PYTHONPATH = "."
python -m pytest backend/tests/ -q

# Phase 1 Definition of Done checks
.\scripts\validate-phase1.ps1

# Phase 2 Definition of Done checks
.\scripts\validate-phase2.ps1

# Phase G — Metric Registry seed + golden-question harness baseline
.\scripts\seed-metric-registry.ps1
.\scripts\run-golden-eval.ps1 --harness-baseline --write-gate
```

Owner sign-off: `knowledge/07-testing/sign-off.md` (Phase 1) · `knowledge/07-testing/phase-2-sign-off.md` (Phase 2)

Phase G→K roadmap: `knowledge/05-architecture/phases/phase-g-to-k-grand-roadmap.md` · Phase G handoff: `phases/phase-g-foundation.md`

---

## Local data cleanup (Phase D / prep for Phase E)

Scratch files under `data/local/local_data/` (reserved for future parquet / job-scoped models), aged logs, and terminal chat jobs can be cleared safely:

```powershell
.\scripts\cleanup-local-data.ps1              # default: logs/jobs older than 14 days
.\scripts\cleanup-local-data.ps1 -Days 7 -JobDays 30
.\scripts\cleanup-local-data.ps1 -WhatIf      # dry-run
```

**Never deleted by this script:**

| Path | Why |
|------|-----|
| `data/local/team_memory/` | Onboarding baseline |
| `data/local/knowledge/` | Glossary, discovery, SQL reference, **metric_registry.json** |
| `data/local/eval/` | Golden questions + eval results (Phase G3 baseline) |
| `data/local/models/approved/` | Phase E promoted models (convention reserved now) |

### Windows Task Scheduler (optional)

1. Open **Task Scheduler** → Create Basic Task → trigger Daily (e.g. 03:00)
2. Action: **Start a program**
   - Program: `powershell.exe`
   - Arguments: `-NoProfile -ExecutionPolicy Bypass -File "C:\Projects\ai-analytic-multiagent\scripts\cleanup-local-data.ps1"`
   - Start in: `C:\Projects\ai-analytic-multiagent`

---

## Architecture

```
User ──► Streamlit UI ──► FastAPI ──► LangGraph Orchestrator
                                           │
         Explore (collaborative)             │ Trusted (router)
                     ┌─────────────────────┼─────────────────────┐
                     ▼                     ▼                     ▼
               Data Engineer          Data Analyst         Data Scientist
                     │                     │                     │
                     └──────────► Business Analyst ◄──────────┘
                                           │
                                    CEO Briefing + Feedback
                                           │
              Discovery + Knowledge ───────┤
                     │                     │
              [HITL Approval]         Fabric DW (read-only)
                     │
              Trusted JSON + Backlog + Knowledge (data/local/)
```

| Agent | Role |
|-------|------|
| **Data Engineer** | Schema, discovery, semantic layer; HITL for layer updates |
| **Data Analyst** | T-SQL with schema context pack, SQL retry, Quality Bar D |
| **Data Scientist** | Critique, sanity checks, statistical framing |
| **Business Analyst** | Metric definitions, CEO narrative, KPI alignment (hybrid HITL) |

**Modes:** `Explore` (draft) · `Trusted` (approved definitions only)

---

## Key API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/chat/` | Submit question → **202 + job_id** (poll via jobs API) |
| `GET` | `/api/v1/jobs/{job_id}` | Job status + per-agent progress + result |
| `GET` | `/api/v1/jobs/?thread_id=&active=true` | Find active job (UI re-attach) |
| `POST` | `/api/v1/jobs/{job_id}/cancel` | Cancel a running job |
| `GET` | `/api/v1/fabric/health` | Fabric connection check |
| `POST` | `/api/v1/themes/scan` | Schema scan → theme proposals |
| `GET/POST` | `/api/v1/backlog/` | Insight backlog (JSON) |
| `POST` | `/api/v1/backlog/{id}/export` | Thai Markdown handoff |
| `GET/POST` | `/api/v1/semantic/promote/{id}/…` | Trusted promotion HITL |
| `GET` | `/api/v1/validation/phase1` | Phase 1 DoD checklist |
| `GET` | `/api/v1/validation/phase2` | Phase 2 DoD checklist |
| `POST` | `/api/v1/discovery/{theme_id}/run` | Theme discovery pipeline |
| `GET/POST` | `/api/v1/knowledge/glossary` | Field glossary CRUD |
| `POST` | `/api/v1/knowledge/sap-tables/import` | Import SAP DD02T CSV |
| `GET` | `/api/v1/knowledge/sap-tables/stats` | SAP import status |
| `GET` | `/api/v1/knowledge/sap-tables/lookup/{table}` | Lookup description |
| `GET/POST` | `/api/v1/briefings/{theme_id}` | Multi-role CEO briefs |
| `POST` | `/api/v1/feedback/{theme_id}` | CEO feedback on briefs |
| `POST` | `/api/v1/approval/` | Approve semantic layer updates |

---

## Project structure

```
├── backend/app/
│   ├── agents/           # LangGraph orchestrator + DE/Analyst/Scientist
│   ├── api/routes/       # chat, fabric, themes, backlog, semantic, validation
│   ├── services/         # fabric_connector, sql_guard, stores, promotion
│   └── schemas/
├── frontend/
│   ├── app.py            # Streamlit main
│   └── components/       # theme, backlog, promotion, validation panels
├── data/
│   ├── templates/        # backlog + semantic JSON templates (committed)
│   └── local/            # runtime data — gitignored
├── scripts/
│   ├── run-backend.ps1
│   ├── run-frontend.ps1
│   ├── setup-ollama-models.ps1
│   └── validate-phase1.ps1
├── knowledge/            # discovery → build sprints, sign-off
└── .env.example
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| ถามแล้วรอนานไม่ได้คำตอบ | คำถามรันเป็น background job แล้ว — UI แสดง progress รายตำแหน่ง; refresh browser ได้ ระบบ re-attach อัตโนมัติ (thread เดิมอยู่ใน URL) |
| อยากดูว่างานพังเพราะอะไร | ดู `data/local/logs/backend.log` (มี stack trace) หรือ `GET /api/v1/jobs/{job_id}` ดู step timeline |
| Backend restart กลางคัน | งานที่ค้างถูก mark เป็น failed ตอน start ใหม่ — คำตอบบางส่วนของ agent ที่เสร็จแล้วยังอยู่ในประวัติแชท |
| Fabric not configured | Fill `FABRIC_*` in `.env`; restart backend |
| `Invalid client secret` | Use secret **Value**, not Secret ID |
| Wrong tables / workspace | Copy connection string from the **correct** Warehouse; grant SP in that workspace |
| `ODBC Driver 18` not found | `winget install Microsoft.msodbcsql.18` |
| Ollama OOM | Use `qwen2.5-coder:7b` in `.env` temporarily |
| UI cannot reach API | `BACKEND_URL=http://127.0.0.1:8000` (not `http://backend:8000`) |

---

## Documentation

| Topic | Path |
|-------|------|
| PRD & acceptance criteria | `knowledge/03-prd/` |
| Architecture & ADRs | `knowledge/05-architecture/` |
| Build sprints | `knowledge/06-sprints/` |
| Phase 1 sign-off | `knowledge/07-testing/sign-off.md` |
| Phase 2 sign-off | `knowledge/07-testing/phase-2-sign-off.md` |

---

## Legacy (not Phase 1 runtime)

Docker Compose and PostgreSQL remain in the repo for reference but are **not** the primary way to run Phase 1. Use native scripts above.
