"""lesson_miner tests (Phase J) — cluster PDCA failures into sql_lessons.json."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.services import lesson_miner


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


def test_mine_lessons_clusters_by_error_class(tmp_path: Path):
    jsonl = tmp_path / "pdca_failures.jsonl"
    _write_jsonl(
        jsonl,
        [
            {"error": "Invalid column name 'X'. (42S22)", "at": "2026-07-01T00:00:00Z"},
            {"error": "Invalid column name 'Y'. (42S22)", "at": "2026-07-02T00:00:00Z"},
            {"error": "Invalid column name 'Z'. (42S22)", "at": "2026-07-03T00:00:00Z"},
            {"error": "HYT00 Query timeout expired", "at": "2026-07-04T00:00:00Z"},
            {"error": "syntax near FROM", "at": "2026-07-05T00:00:00Z"},
        ],
    )
    lessons = lesson_miner.mine_lessons(jsonl_path=jsonl, top_n=10)
    assert lessons[0]["error_class"] == "invalid_column"
    assert lessons[0]["count"] == 3
    assert "ชื่อคอลัมน์" in lessons[0]["lesson_th"]
    classes = {L["error_class"] for L in lessons}
    assert classes == {"invalid_column", "timeout", "generic"}


def test_mine_lessons_empty_file(tmp_path: Path):
    jsonl = tmp_path / "empty.jsonl"
    jsonl.write_text("", encoding="utf-8")
    assert lesson_miner.mine_lessons(jsonl_path=jsonl) == []


def test_mine_lessons_missing_file(tmp_path: Path):
    assert lesson_miner.mine_lessons(jsonl_path=tmp_path / "nope.jsonl") == []


def test_write_load_format_roundtrip(tmp_path: Path):
    out = tmp_path / "sql_lessons.json"
    lessons = [
        {
            "error_class": "timeout",
            "count": 4,
            "lesson_th": "timeout lesson",
            "example_error": "timed out",
            "last_seen": "2026-07-18T00:00:00Z",
        }
    ]
    lesson_miner.write_lessons(lessons, path=out)
    loaded = lesson_miner.load_lessons(path=out)
    assert loaded == lessons
    ctx = lesson_miner.format_lessons_context(path=out)
    assert "Known SQL lessons" in ctx
    assert "[timeout]" in ctx
    assert "timeout lesson" in ctx


def test_format_lessons_context_empty(tmp_path: Path):
    assert lesson_miner.format_lessons_context(path=tmp_path / "missing.json") == ""


def test_run_lesson_mining_end_to_end(tmp_path: Path):
    jsonl = tmp_path / "pdca_failures.jsonl"
    _write_jsonl(
        jsonl,
        [
            {"error": "could not connect to server", "at": "t1"},
            {"error": "Login failed for user", "at": "t2"},
        ],
    )
    out = tmp_path / "lessons.json"
    summary = lesson_miner.run_lesson_mining(jsonl_path=jsonl, output_path=out, top_n=5)
    assert summary["total_failures"] == 2
    assert summary["lessons_written"] == 1
    assert Path(summary["output_path"]).exists()
    assert lesson_miner.load_lessons(path=out)[0]["error_class"] == "connection"
