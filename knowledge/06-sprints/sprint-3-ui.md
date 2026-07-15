# Build Sprint 3 — Explore/Trusted UI & Backlog Sidebar

**Stage:** 06 Build  
**Date:** 2026-07-15  
**Stories:** UI-1, UI-2, UI-3  
**Status:** Complete — pending commit sign-off

---

## Delivered

| Story | Implementation |
|-------|----------------|
| UI-1 | Mode radio Explore/Trusted + draft/trusted badges on responses |
| UI-2 | `st.status` progress during chat ("กำลังวิเคราะห์...") |
| UI-3 | Sidebar backlog list, feedback textarea, status update via PATCH API |

## Files

- `frontend/app.py` — reworked layout
- `frontend/components/status_bar.py` — Fabric health + mode selector
- `frontend/components/backlog_panel.py` — backlog CRUD UI
- `frontend/components/api_client.py` — shared HTTP helpers
- `frontend/components/chat_box.py` — mode badges
- `frontend/components/approval_panel.py` — use api_client

## Manual Test

```powershell
.\scripts\run-backend.ps1
.\scripts\run-frontend.ps1
```

1. Toggle Explore / Trusted in sidebar
2. Send chat — see status spinner + draft badge (Explore)
3. POST backlog item via API — appears in sidebar
4. Update feedback/status from sidebar

## Next Sprint

Build Sprint 4 — EXPLORE-1, UI-4 (schema scan + theme selection)
