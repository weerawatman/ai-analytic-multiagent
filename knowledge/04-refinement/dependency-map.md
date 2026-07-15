# Dependency Map — Phase 1 Backlog

**Date:** 2026-07-15

---

## Visual

```
INFRA-1 (Fabric connect)
    ├── INFRA-2 (SQL guard)
    ├── INFRA-3 (Health)
    └── INFRA-4 (Native config)
            │
            ├── STORE-1 (SQLite) ──┐
            ├── STORE-2 (Backlog) ─┼── UI-3 (Backlog sidebar)
            └── STORE-3 (Semantic) ─┘
                    │
            UI-1 (Mode toggle)
                    │
            EXPLORE-1 (Schema scan) ── UI-4 (Theme pick)
                    │
            AGENT-1 (Prompts) ── EXPLORE-2 (Quality Bar D)
                    │
            HANDOFF-1 (Export)
                    │
            TRUST-1 (Promotion) ── depends on STORE-3, HANDOFF-1 feedback flow
                    │
            VALID-1 (E2E) ── depends on all above
```

---

## Critical Path

```
INFRA-1 → INFRA-2 → STORE-2 → EXPLORE-1 → EXPLORE-2 → HANDOFF-1 → TRUST-1 → VALID-1
```

**Longest pole:** EXPLORE-1 (schema scan on large SAP DW) + EXPLORE-2 (Quality Bar D with local LLM)

---

## Parallelizable (after INFRA-1)

| Track A | Track B |
|---------|---------|
| STORE-1, STORE-2, STORE-3 | UI-1, UI-2 (mock API) |
| INFRA-4 scripts | AGENT-1 prompt drafts |

---

## Blockers

| Blocker | Blocks | Resolution |
|---------|--------|------------|
| Fabric SP auth not working | All query stories | M1 spike first |
| Ollama 14B quality insufficient | EXPLORE-2 | Switch to 32B |
| No theme selected | EXPLORE-2 deep dive | EXPLORE-1 must complete |

---

## Traceability

| Backlog file | Milestone |
|--------------|-----------|
| `backlog/INFRA.md` | M1 |
| `backlog/STORE.md` | M2 |
| `backlog/UI.md` | M3, M4 |
| `backlog/EXPLORE-TRUST.md` | M4–M8 |
