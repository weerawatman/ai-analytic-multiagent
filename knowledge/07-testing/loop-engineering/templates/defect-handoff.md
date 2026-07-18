# Defect handoff — {{def_id}}

> **วันที่:** {{date}}
> **From run:** {{run_id}}
> **Scenario:** {{scn_id}}
> **Severity:** low | medium | high | blocker
> **Category:** env | llm | sql | code | test | human-gate

## Summary (Thai, one paragraph)

{{summary_th}}

## Repro

1. Preconditions: …
2. Command / UI steps: …
3. Observed: …
4. Expected: …

## Evidence (pointers only)

- Raw run dir: `data/local/qa/loop-engineering/runs/{{run_id}}/`
- Log hint: `data/local/logs/backend.log` (sanitized excerpts only in committed docs)
- Related tests: …

## Suggested owner

| Category | Delegate |
|----------|----------|
| env / launcher | devops-release / main agent |
| llm / Ollama | main agent (config) |
| sql / provenance | main agent (fabric/pg) |
| code defect | main Dev agent |
| coverage gap | qa-test-engineer |
| Trusted / KPI / production | **Owner (human)** — stop |

## Allowed fix scope

- Minimal product fix + targeted tests
- Do **not** weaken conformance tests
- Do **not** commit/push without user request
- Max repair rounds remaining: {{rounds_left}}

## Resolution

- [ ] Fixed
- [ ] Won't fix (reason)
- [ ] Needs human gate
- [ ] Regression re-run: pass / fail
