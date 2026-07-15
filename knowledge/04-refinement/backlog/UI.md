# UI-1: Explore / Trusted Mode Toggle

**Epic:** M3 UI  
**Priority:** Must  
**Estimate:** S  
**AC:** AC-3, AC-8

## User Story
As a Data Engineer, I want to switch between Explore and Trusted modes so that I always know output trust level.

## Tasks
- [ ] Streamlit toggle + session state
- [ ] Pass `mode` to chat API
- [ ] Visual badge on responses (Draft vs Trusted)

## Acceptance
- Given Explore mode, When response shown, Then "Draft · รอ validate" badge visible

---

# UI-2: Progress & Agent Status

**Epic:** M3 UI  
**Priority:** Should  
**Estimate:** S  
**AC:** NFR-P3

## User Story
As a Data Engineer, I want to see progress during long agent runs so that I know the system is working.

## Tasks
- [ ] Spinner + status text during chat request
- [ ] Optional: show active agent name
- [ ] Timeout message in Thai if Ollama slow

## Acceptance
- Given long-running query, When waiting, Then progress indicator shown (not blank screen)

---

# UI-3: Backlog Sidebar

**Epic:** M3 UI  
**Priority:** Must  
**Estimate:** M  
**AC:** AC-4, AC-6

## User Story
As a Data Engineer, I want to see and manage backlog items in the sidebar.

## Tasks
- [ ] List items with status color/icon
- [ ] Expander for detail view
- [ ] Feedback textarea + status dropdown
- [ ] Save / Promote buttons

## Acceptance
- Given backlog items exist, When sidebar opened, Then items listed with status

---

# UI-4: Theme Selection

**Epic:** M4 Schema Scan  
**Priority:** Must  
**Estimate:** M  
**AC:** AC-2

## User Story
As a Data Engineer, I want to pick from 3 proposed themes so that exploration has focus.

## Tasks
- [ ] Display theme cards after scan
- [ ] Select button sets active theme in session
- [ ] Show starter questions as chips

## Acceptance
- Given 3 themes returned, When user selects one, Then theme stored and Explore uses it
