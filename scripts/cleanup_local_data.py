"""Purge terminal jobs for cleanup-local-data.ps1 (keeps knowledge/team_memory)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.job_store import init_jobs_db, purge_old_terminal_jobs
from backend.app.services.local_paths import ensure_local_structure


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge old terminal chat/onboarding jobs")
    parser.add_argument("--job-days", type=int, default=14)
    args = parser.parse_args()
    ensure_local_structure()
    init_jobs_db()
    n = purge_old_terminal_jobs(older_than_days=args.job_days)
    print(f"purged_jobs={n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
