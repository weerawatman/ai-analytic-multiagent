# AGENTS.md — Universal Agent Contract

This file defines how AI agents should interact with this repository.

---

## Project Configuration

```
Project:     AI Analytics Multi-Agent (Fabric Insight Explorer)
Description: Local AI Data Team for deep insight exploration on Microsoft Fabric DW, with Explore/Trusted knowledge loop
Status:      build
Created:     2026-07-15
Updated:     2026-07-18
Owner:       Data Engineer (solo Phase 1)
```

**Status** reflects current focus. Valid values: `discovery`, `design`, `prd`, `refinement`, `architecture`, `build`, `testing`, `deployment`, `operations`.

---

## General Rules

1. **Read before you write.** Check `knowledge/` before producing artifacts.
2. **Respect preconditions.** Do not skip stages without required artifacts.
3. **Write artifacts to the correct location.** See stage definitions below.
4. **Flag human gates.** Stop and ask before scope, architecture, or production decisions.
5. **Maintain context chain.** Reference upstream artifacts (discovery → PRD → architecture).
6. **Phase 1 priority:** Output quality and correctness over speed or UI polish.
7. **Fabric is read-only.** Never execute write DDL/DML against `WH_SAP_PRD` without explicit human approval.

---

## Key Artifacts (Current)

| Stage | Artifact | Path |
|-------|----------|------|
| Discovery | Discovery brief | `knowledge/01-discovery/discovery-brief.md` |
| Design | User journeys | `knowledge/02-design/user-journeys/` |
| Design | Design decisions | `knowledge/02-design/design-decisions.md` |
| PRD | Product requirements | `knowledge/03-prd/prd.md` |
| PRD | Constraints | `knowledge/03-prd/constraints.md` |
| PRD | NFRs | `knowledge/03-prd/nfr.md` |
| Architecture | System design | `knowledge/05-architecture/architecture/Architecture.md` |
| Architecture | Tech stack | `knowledge/05-architecture/tech-stack.md` |
| Architecture | Phase 1 plan | `knowledge/05-architecture/phases/phase-1.md` |
| Architecture | **Roadmap G→K (self-learning analytics)** | `knowledge/05-architecture/phases/phase-g-to-k-grand-roadmap.md` |
| Architecture | Phase gates (audit trail) | `knowledge/05-architecture/phases/gates/` |
| Architecture | ADRs | `knowledge/05-architecture/adr/` |
| Testing | Stage 07 index + owner sign-offs | `knowledge/07-testing/STAGE.md` |
| Testing | **Loop Engineering QA** (readiness scenarios, run reports) | `knowledge/07-testing/loop-engineering/` |
| Testing | Loop Engineering skill (orchestrator) | `.cursor/skills/engineering-qa/loop-engineering-qa/` |

---

## Phase 1 Summary (Locked Decisions)

- **Users:** Solo Data Engineer (BA/DA later)
- **Data source:** Microsoft Fabric DW primary; since Phase F a PostgreSQL WH_Silver mirror is a **labeled auto-fallback** (never silent — provenance on every result; see `phases/phase-f-postgres-fallback.md`)
- **Auth to DW:** Service Principal, SELECT-only + SQL allowlist guard
- **Modes:** `Explore` (draft) and `Trusted` (validated definitions)
- **Quality bar:** Heavy validation (SQL, assumptions, sanity checks, sample rows)
- **Storage:** JSON (semantic/backlog) + SQLite (chat history) under `data/local/`
- **Runtime:** Native on Windows (FastAPI + Streamlit + Ollama)
- **LLM:** Local Ollama ~14B default, switchable to ~32B
- **Language:** Thai for UI/reports; English for SQL/technical metadata
- **Phase 1 done when:** One theme completes full loop + at least one Trusted playbook

---

## Phase G–K Delegation Rules (binding for any AI implementing the roadmap)

Before implementing **any** part of phases G–K (self-learning analytics), you MUST:

1. Read `knowledge/05-architecture/phases/phase-g-to-k-grand-roadmap.md` **§4 Delegation Guardrails** in full, and follow its Handoff Protocol (§4.4): create a phase doc from `phases/_TEMPLATE-phase.md` before writing any code.
2. Treat `backend/tests/test_roadmap_conformance.py` as a **binding contract** — it enforces the roadmap invariants automatically (skipped until each module exists, then enforced forever). Never weaken, skip, or delete these tests to make a build pass.
3. Any deviation from locked decisions or canonical names requires **owner approval first**, recorded in the phase doc's Deviation Log — never "do first, report later".
4. A phase is only "done" when its gate artifact exists in `phases/gates/` with real evidence (see `gates/README.md`).

---

## Human Gates

| Gate | When |
|------|------|
| PRD sign-off | Before refinement/build |
| Architecture sign-off | Before build sprint |
| Trusted promotion | Before insight enters semantic layer |
| DW change suggestions | Before any write to Fabric (Phase 1: never auto-apply) |

---

## Feedback Loop

```
Explore → Backlog → BA/DA validation → Trusted semantic/playbook → future Explore
```

Operations feedback (Phase 2+) feeds back into `knowledge/01-discovery/`.

---

## Documentation & Handover Contract (binding)

Keep **PROJECT_OVERVIEW.md**, **phase-summaries/**, **README.md**, and **docs/diagrams/SYSTEM_DIAGRAMS.md** aligned with the repo whenever the system changes. This contract applies to AI agents and human developers.

### Update triggers — edit docs in the same change set when you:

| Trigger | Minimum updates |
|---------|-----------------|
| New/changed API, route, job kind, or agent graph | `PROJECT_OVERVIEW.md` §4–6; `README.md` if run/setup changes; relevant diagram(s) in `docs/diagrams/SYSTEM_DIAGRAMS.md` (§1–3) |
| Architecture, data-source fallback, or source resolution | `PROJECT_OVERVIEW.md` §4; diagram §1, §5 |
| Insight, learning, digest pipelines, or scheduler jobs | `PROJECT_OVERVIEW.md` §4–6; diagram §6, §7 |
| Knowledge / Trusted lifecycle or promotion flow | `knowledge/07-testing/` when sign-off; diagram §8 |
| Phase G–K scope, gate, or conformance test | Phase doc under `knowledge/05-architecture/phases/`; gate in `gates/`; `phase-summaries/phase-{x}.md`; diagram §9, §10 if readiness changes |
| Production/live verification (or lack thereof) | `PROJECT_OVERVIEW.md` §3 + §11; phase summary **สถานะ** line; diagram §10 |
| Remaining work reprioritized | `PROJECT_OVERVIEW.md` §11; active phase summary **งานคงเหลือ** |
| Test count or pytest scope changes | `PROJECT_OVERVIEW.md` §9; phase summary **ผลเทสต์** |
| Trusted promotion, sign-off, or owner gate | `knowledge/07-testing/`; `PROJECT_OVERVIEW.md` §3 handover items |
| Loop Engineering readiness run / new SCN / open QA defects | Sanitized report under `knowledge/07-testing/loop-engineering/`; `PROJECT_OVERVIEW.md` §9/§11; diagram §10/§11 if readiness story changes |

If unsure whether a change triggers an update, update **PROJECT_OVERVIEW.md** §11 and note what was not verified.

### Loop Engineering QA (readiness — not a human gate)

- Entrypoint skill: `.cursor/skills/engineering-qa/loop-engineering-qa/` — invoke when the user asks to test the system / check readiness before real testing (`ทดสอบระบบ`, `ความพร้อม`, etc.).
- Runner: `scripts/run-readiness-check.ps1` (L0 env, L1 pytest, optional L2 live/golden).
- **QA recommends readiness only.** It does not approve Trusted promotion, KPI formulas, PRD/architecture, or production-verified status, and does not replace G–K gate artifacts.
- Semi-auto authority: triage + fix + regression; **stop before commit/push** unless the user explicitly asks.
- Never weaken `test_roadmap_conformance.py` to force a green run.

### Phase summary requirements (`phase-summaries/`)

- One file per closed or partially closed phase: `phase-{letter}.md` (see `phase-summaries/README.md`).
- Required sections: **สิ่งที่ทำแล้ว**, **งานคงเหลือ**, **เกตที่ค้าง**, **commits ที่เกี่ยวข้อง**, **วันที่**.
- Link to the phase doc and gate artifact when they exist.
- After **push to remote**, add the commit hash(es) and push date — not before push (avoid stale hashes).
- Do not invent completed work; cite phase doc, gate, or commit evidence only.

### Code-complete vs production-verified (honesty rule)

| Label | Meaning | Allowed wording |
|-------|---------|-----------------|
| **Code-complete** | Merged code + pytest green | "โค้ดเสร็จ", "tests passed", module exists |
| **Production-verified** | Live env + owner/metric evidence | "ยืนยันบน production/live", gate signed, §10 criteria met |

Never mark production-verified from tests alone. If live gates are open, say so explicitly in §3, §11, and the phase summary **สถานะ** line.

### README sync

`README.md` is the install/run entry point. When setup, scripts, env vars, or default run flow change, update README in the same PR/session. Point deep context to `PROJECT_OVERVIEW.md` — do not duplicate the full overview in README.

### System diagrams sync

`docs/diagrams/SYSTEM_DIAGRAMS.md` is a maintained handover artifact — not optional illustration. When architecture, agent order/graph, job kinds, data-source fallback, insight/learning/digest pipelines, knowledge/Trusted lifecycle, or phase readiness changes, update the relevant Mermaid diagram(s) in the same change set. Keep diagram style consistent (Thai labels, English technical terms, `flowchart` / `sequenceDiagram` / `stateDiagram-v2` only). Apply the same **code-complete vs production-verified** honesty rule: label live gates and pending verification on diagrams exactly as in overview and phase summaries — never imply production-verified from tests alone. If diagrams cannot be updated in time, note **diagram debt** in the phase summary and overview §11.

### Docs review before phase handover

Before calling a phase "done" or handing off to the next owner/session:

1. Phase doc Definition of Done checked with real evidence.
2. Gate artifact exists in `phases/gates/` (G–K) or sign-off doc updated (Phase 1–2).
3. `phase-summaries/phase-{x}.md` written or updated per template.
4. `PROJECT_OVERVIEW.md` header date + reference commit; §3, §11, and §15 reflect current truth.
5. `README.md` still accurate for run/setup.
6. `docs/diagrams/SYSTEM_DIAGRAMS.md` — relevant diagram(s) match real behavior, or diagram debt is noted honestly.
7. No contradiction between overview, summaries, gates, diagrams, and `test_roadmap_conformance.py`.

Cursor enforces a short checklist via `.cursor/rules/project-documentation-governance.mdc` (alwaysApply). **This section in AGENTS.md is the source of truth.**
