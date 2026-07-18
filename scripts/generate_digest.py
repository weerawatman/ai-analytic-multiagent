"""Generate a board digest (Phase K) — no new job kind; script trigger like mine_lessons."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def _main(week_key: str | None, polish: bool | None) -> int:
    from backend.app.services import digest_service

    doc = await digest_service.generate_digest(week_key=week_key, polish=polish)
    print(json.dumps({"week_key": doc.get("week_key"), "counts": doc.get("counts"), "path": doc.get("path")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Phase K board digest")
    parser.add_argument("--week", default=None, help="ISO week key yyyy-ww")
    parser.add_argument("--polish", action="store_true", help="Force Claude polish")
    parser.add_argument("--no-polish", action="store_true", help="Skip polish")
    args = parser.parse_args()
    polish = True if args.polish else (False if args.no_polish else None)
    raise SystemExit(asyncio.run(_main(args.week, polish)))
