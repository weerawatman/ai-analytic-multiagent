"""Sub-step notes for the active job timeline (Phase G1).

Agents call ``note_substep(thread_id, text)`` to surface mid-step progress
(e.g. "SQL รอบที่ 2/3") without creating a new timeline entry.
"""

from __future__ import annotations

from backend.app.services import job_store

# Prefer chat jobs; fall back to any active job for the thread.
_KIND_PREFERENCE = ("chat", "onboarding", "deep_onboarding", "consult")


def note_substep(thread_id: str, text: str) -> None:
    """Attach a short note to the current running step of the thread's active job."""
    if not thread_id or not text:
        return
    job = None
    for kind in _KIND_PREFERENCE:
        job = job_store.find_active_job(kind, thread_id)
        if job:
            break
    if job is None:
        active = job_store.list_jobs(thread_id=thread_id, active_only=True, limit=1)
        job = active[0] if active else None
    if job is None:
        return

    note = text.strip()[:500]
    progress = list(job.get("progress") or [])
    entry = next((p for p in reversed(progress) if p.get("status") == "running"), None)
    if entry is None and job.get("current_step"):
        entry = {
            "step": job["current_step"],
            "status": "running",
            "started_at": job.get("started_at") or job_store._utc_now(),
            "ended_at": None,
            "note": None,
        }
        progress.append(entry)
    if entry is None:
        return
    entry["note"] = note
    job_store.update_job(job["id"], progress=progress)
    job_store.touch_job(job["id"])
