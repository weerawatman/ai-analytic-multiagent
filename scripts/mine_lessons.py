"""Manually trigger SQL-failure lesson mining (Phase J).

No automatic scheduling yet — adding a job kind for this needs owner
sign-off first (see phase-j-learning-loops.md Deviation Log). Run this
script by hand or wire it into an external scheduler (e.g. Windows Task
Scheduler, same convention as cleanup-local-data.ps1) until then.
"""

from __future__ import annotations

import json


def _main() -> int:
    from backend.app.services.lesson_miner import run_lesson_mining
    from backend.app.services.local_paths import ensure_local_structure

    ensure_local_structure()
    summary = run_lesson_mining()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
