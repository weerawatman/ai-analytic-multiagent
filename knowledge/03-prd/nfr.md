# Non-Functional Requirements — Phase 1

---

## Quality (Primary)

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-Q1 | Explore output completeness | 100% of saved backlog items pass Quality Bar D |
| NFR-Q2 | SQL executability | ≥95% generated SQL runs without syntax error on first or second attempt |
| NFR-Q3 | Assumption transparency | Every backlog item lists grain, filters, and open questions |
| NFR-Q4 | Trusted accuracy | Zero auto-promotion — all Trusted entries human-approved |

---

## Performance (Secondary — Not Optimized)

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-P1 | Single Explore analysis latency | No hard SLA — user accepts slow (~14B–32B local) |
| NFR-P2 | Schema scan | Complete within reasonable interactive wait (<10 min acceptable) |
| NFR-P3 | UI responsiveness | Streamlit must remain usable during long agent runs (progress/status) |

---

## Reliability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-R1 | Fabric connection recovery | Clear error message + retry on transient failures |
| NFR-R2 | State persistence | Chat and backlog survive app restart |
| NFR-R3 | Ollama unavailable | Graceful degradation with user-visible error |

---

## Security

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-S1 | SQL injection prevention | Parameterized queries where applicable; allowlist for agent-generated SQL |
| NFR-S2 | Secret handling | All credentials in `.env` only |
| NFR-S3 | Data at rest | Business data only in `data/local/` (gitignored) |
| NFR-S4 | Network exposure | localhost binding only |

---

## Maintainability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-M1 | Model swap | Change Ollama model via env without code change |
| NFR-M2 | Documentation | PRD + Architecture + ADRs in `knowledge/` |
| NFR-M3 | Agent extensibility | Add Phase 2 features without breaking Explore/Trusted contract |

---

## Usability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-U1 | Language | Thai UI labels and reports; English SQL/technical |
| NFR-U2 | Mode clarity | User always sees current mode (`Explore` vs `Trusted`) |
| NFR-U3 | Draft labeling | Explore outputs visibly marked as draft |

---

## Scalability (Phase 2+ Placeholder)

| ID | Requirement | Notes |
|----|-------------|-------|
| NFR-X1 | Multi-user | Deferred — design storage to allow future auth |
| NFR-X2 | Team size ≤10 | No hard scaling target in Phase 1 |
