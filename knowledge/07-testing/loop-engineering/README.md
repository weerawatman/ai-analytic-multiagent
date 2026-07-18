# Loop Engineering QA

ศูนย์กลางเดียวสำหรับ **ทดสอบความพร้อมก่อนใช้งานจริง** (Test → Triage → Fix → Verify → Report)

ไม่ใช่ runtime agent ใน LangGraph (ไม่แตะ DE→DS→DA→BA)

## Ownership

| Role | Responsibility |
|------|----------------|
| Skill `loop-engineering-qa` | Orchestrate the loop when the user asks for readiness testing |
| `qa-test-engineer` | Design/fill pytest coverage gaps |
| Dev (main agent) | Fix product defects (when user allows semi-auto) |
| `roadmap-conformance-reviewer` | G–K gate / invariant decisions |
| Owner (human) | Commit/push, Trusted, KPI, production-verified |

## Authority (locked)

- Semi-automatic: run tests, triage, delegate fixes, rerun regression.
- **Stop before commit/push** unless the user explicitly asks.
- Max **2–3 repair rounds** per defect cluster.
- Never weaken, skip, or delete `test_roadmap_conformance.py` invariants to make a build pass.
- Never declare production-verified from offline tests alone.

## Layout

```text
loop-engineering/
├── README.md                 # this file
├── scenario-catalog.md       # SCN-* definitions
├── templates/
│   ├── run-report.md
│   ├── defect-handoff.md
│   └── readiness-assessment.md
├── run-reports/              # sanitized committed summaries
├── defect-handoffs/          # defect packets
└── readiness/                # QA recommendation only
```

Raw evidence (ignored): `data/local/qa/loop-engineering/runs/<run-id>/`

## Quick start

1. User: “ทดสอบความพร้อมก่อนทดสอบจริง” (or equivalent).
2. Agent loads skill → runs `.\scripts\run-readiness-check.ps1`.
3. Triage failures → fix or stop for human gate.
4. Write sanitized report under `run-reports/` + `readiness/`.
5. Ask user before commit/push.

## Related

- Skill: `.cursor/skills/engineering-qa/loop-engineering-qa/SKILL.md`
- Runner: `scripts/run-readiness-check.ps1`
- Stage index: [`../STAGE.md`](../STAGE.md)
