# EXPLORE-1: Schema Scan & Theme Ranking

**Epic:** M4 Schema Scan  
**Priority:** Must  
**Estimate:** L  
**AC:** AC-2

## User Story
As a Data Engineer, I want the DE agent to scan Fabric schema and propose 3 themes in Thai.

## Tasks
- [ ] Query INFORMATION_SCHEMA / sys tables for metadata
- [ ] Group tables into candidate domains (heuristic + LLM summary)
- [ ] Rank top 3 by richness signals (row counts if cheap, column count, naming)
- [ ] Generate Thai rationale + starter questions per theme
- [ ] `POST /api/v1/themes/scan` endpoint

## Acceptance
- Given connected Fabric, When scan triggered, Then 3 themes returned in Thai with starter questions

---

# EXPLORE-2: Quality Bar D Assembly

**Epic:** M5 Quality Pipeline  
**Priority:** Must  
**Estimate:** L  
**AC:** AC-4

## User Story
As a Data Engineer, I want Explore outputs assembled to Quality Bar D before saving.

## Tasks
- [ ] Orchestrator post-processing step after agent nodes
- [ ] Scientist node: alternative SQL + sanity check
- [ ] Enforce required fields before backlog save allowed
- [ ] Sample data capture (limited rows) attached to candidate

## Acceptance
- Given Explore completes, When save clicked, Then all Q1–Q6 fields populated or save blocked with message

---

# AGENT-1: Agent Prompt Updates for Phase 1

**Epic:** M5 Quality Pipeline  
**Priority:** Must  
**Estimate:** M  
**AC:** AC-3, AC-4

## User Story
As a Data Engineer, I want agents optimized for deep Thai/English mixed analysis on Fabric SAP data.

## Tasks
- [ ] Update DE prompt: schema context, semantic gaps, theme awareness
- [ ] Update Analyst prompt: Fabric T-SQL, assumption listing, sample queries
- [ ] Update Scientist prompt: challenge assumptions, alternative angles
- [ ] Default model config ~14B with env override

## Acceptance
- Given Explore question, When agents run, Then response includes assumptions and questions for BA/DA in Thai

---

# HANDOFF-1: Thai Markdown Export

**Epic:** M6 Handoff  
**Priority:** Must  
**Estimate:** M  
**AC:** AC-5, AC-6

## User Story
As a Data Engineer, I want to export a Thai report for BA/DA discussions.

## Tasks
- [ ] Report template (Markdown, Thai sections)
- [ ] `POST /api/v1/backlog/{id}/export`
- [ ] Save to `data/local/exports/`
- [ ] Download button in Streamlit

## Acceptance
- Given backlog item, When export clicked, Then `.md` file created with SQL, assumptions, samples, BA/DA questions

---

# TRUST-1: Trusted Promotion HITL

**Epic:** M7 Trusted  
**Priority:** Must  
**Estimate:** M  
**AC:** AC-7, AC-8

## User Story
As a Data Engineer, I want to preview and approve Trusted promotions with full semantic entry.

## Tasks
- [ ] Promotion preview API (metric, playbook, example Q)
- [ ] Extend approval panel for Trusted type
- [ ] Write to semantic JSON on approve
- [ ] Trusted mode constrains Analyst to approved definitions

## Acceptance
- Given validated backlog item, When promote approved, Then Trusted entry exists and Trusted mode uses it

---

# VALID-1: Phase 1 End-to-End Validation

**Epic:** M8 Validation  
**Priority:** Must  
**Estimate:** M  
**AC:** All

## User Story
As a Data Engineer, I want to run one complete theme cycle to prove Phase 1 works.

## Tasks
- [ ] Execute full journey on real Fabric theme
- [ ] Document results in backlog
- [ ] Create `knowledge/07-testing/sign-off.md` draft
- [ ] Owner review

## Acceptance
- PRD Phase 1 Definition of Done checklist all checked
