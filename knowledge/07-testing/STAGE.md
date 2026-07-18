# Stage 07 — Testing & Sign-off

สถานะ: **active** (Loop Engineering QA framework + owner sign-off artifacts)

## Authoritative artifacts

| Artifact | Path | Who may approve |
|----------|------|-----------------|
| Phase 1 sign-off | [`sign-off.md`](sign-off.md) | Owner (human) |
| Phase 2 sign-off | [`phase-2-sign-off.md`](phase-2-sign-off.md) | Owner (human) |
| Loop Engineering QA | [`loop-engineering/`](loop-engineering/) | QA recommends only — not a human gate |
| Phase G–K gates | [`../05-architecture/phases/gates/`](../05-architecture/phases/gates/) | Owner + roadmap-conformance-reviewer |

## Rules

1. **QA recommends readiness; humans approve gates.** A green pytest run or Loop Engineering report never replaces Trusted promotion, KPI definition, PRD, architecture, or production sign-off.
2. Separate **code-complete** / **test-passed** from **production-verified** (see `AGENTS.md` Documentation & Handover Contract).
3. Committed reports under `loop-engineering/` must be sanitized — no secrets, no bulk production row dumps.
4. Raw logs/JUnit live under `data/local/qa/loop-engineering/` (gitignored via `data/local/`).

## How to run readiness

```powershell
.\scripts\run-readiness-check.ps1            # default Level 1 (offline)
.\scripts\run-readiness-check.ps1 -Level 0   # env smoke only
.\scripts\run-readiness-check.ps1 -Level all # L0+L1+L2 opt-in pieces
```

In Cursor, invoke the skill when the user asks to test readiness: `.cursor/skills/engineering-qa/loop-engineering-qa/`.
