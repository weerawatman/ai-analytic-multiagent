---
name: loop-engineering-qa
description: >-
  Runs repository readiness QA (preflight, pytest, conformance, optional live/golden),
  triages failures, delegates fixes, reruns regression, and writes sanitized evidence.
  Use when the user asks to test the system, check readiness before real testing,
  ทดสอบระบบ, ตรวจความพร้อม, readiness, or similar Loop Engineering QA requests.
---

# Loop Engineering QA

Orchestrate **Test → Triage → Fix → Verify → Report** for this repo.
You are an **engineering** orchestrator — not a runtime LangGraph agent (do not change DE→DS→DA→BA).

## Before anything else

1. Read [`AGENTS.md`](../../../../AGENTS.md) and [`knowledge/07-testing/loop-engineering/README.md`](../../../../knowledge/07-testing/loop-engineering/README.md).
2. Load catalog: [`knowledge/07-testing/loop-engineering/scenario-catalog.md`](../../../../knowledge/07-testing/loop-engineering/scenario-catalog.md).
3. Read references as needed:
   - [scenario-levels.md](references/scenario-levels.md)
   - [triage-policy.md](references/triage-policy.md)
   - [report-format.md](references/report-format.md)

## Authority (locked)

- **Semi-auto:** run tests, triage, fix product defects (or delegate), rerun regression.
- **Stop before commit/push** unless the user explicitly asks.
- Max **2–3 repair rounds** per defect cluster.
- Never weaken / skip / delete `backend/tests/test_roadmap_conformance.py` to pass.
- Never declare **production-verified** from offline tests alone.
- Fabric remains **read-only**.

## Workflow

Copy and track:

```text
Loop progress:
- [ ] 1. Confirm scope (Level 0 / 1 / 2 / all)
- [ ] 2. Baseline: git status + note pre-existing dirty tree (do not clobber)
- [ ] 3. Preflight + runner
- [ ] 4. Triage failures
- [ ] 5. Fix or stop for human gate
- [ ] 6. Targeted + full regression
- [ ] 7. Write sanitized run-report + readiness
- [ ] 8. Stop; ask user before commit/push
```

### 1. Scope

Default: **Level 1** (offline) unless user asks for live readiness.

| User intent | Level |
|-------------|-------|
| ตรวจ env / Ollama | 0 |
| ความพร้อมโค้ด / ก่อนทดสอบจริง (default) | 1 |
| ทดสอบแชทจริง / golden | 2 or `all` |

### 2. Run deterministic checks

From repo root:

```powershell
.\scripts\run-readiness-check.ps1 -Level 1
# or: -Level 0 | -Level 2 | -Level all | -IncludeGolden
```

Capture `run_id` and raw dir under `data/local/qa/loop-engineering/runs/<run_id>/`.

### 3. Triage

Classify each failure per [triage-policy.md](references/triage-policy.md):

| Category | Action |
|----------|--------|
| `env` / `llm` | Fix config / advise model size; do not fake green |
| `sql` / `code` | Minimal fix + targeted tests |
| `test` (coverage gap) | Delegate patterns to `qa-test-engineer` agent |
| `human-gate` | **Stop** — document only |

### 4. Fix loop

1. Fix one cluster at a time.
2. Re-run targeted tests, then Level 1 (or agreed level).
3. Stop after 3 failed repair rounds; write defect handoff.

### 5. Report

Write sanitized files using templates in `knowledge/07-testing/loop-engineering/templates/`:

- `run-reports/YYYY-MM-DD-<scope>-<run_id>.md`
- `readiness/YYYY-MM-DD-<scope>-readiness.md`
- `defect-handoffs/DEF-<id>-<slug>.md` when needed

Labels required: code-complete / test-passed / production-verified / human-gate-pending.

### 6. Handoff

Tell the user:

- What passed / failed
- Whether manual Explore is advisable
- Open defects and human gates
- That **commit/push was not done** (unless they asked)

## Delegates (existing agents — do not invent new ones)

- Coverage gaps → `.claude/agents/qa-test-engineer.md`
- G–K gate disputes → `roadmap-conformance-reviewer`
- Scripts / launchers → `devops-release`

## Anti-patterns

- Editing expected golden answers to force pass without owner approval
- Killing unrelated processes on the machine
- Writing DDL/DML to Fabric
- Claiming phase G–K "done" from this skill alone
