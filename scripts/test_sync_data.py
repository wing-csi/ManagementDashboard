"""Tests for scripts/sync_data.py.

Run:  python3 -m pytest scripts/test_sync_data.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from sync_data import resolve_source, sync  # noqa: E402

SAMPLE = '{"schema_version": 2, "generated_at": "2026-07-20T05:00:00+00:00", "tasks": []}'


def test_resolve_source_finds_metrics_in_a_data_repo_clone(tmp_path: Path) -> None:
    repo = tmp_path / "ManagementDashboard-data"
    repo.mkdir()
    (repo / "metrics.json").write_text(SAMPLE, encoding="utf-8")
    assert resolve_source(repo) == repo / "metrics.json"


def test_resolve_source_explains_a_missing_clone(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError) as exc:
        resolve_source(tmp_path / "nope")
    assert "clone" in str(exc.value).lower()


def test_resolve_source_explains_an_empty_clone(tmp_path: Path) -> None:
    """A clone that exists but has no metrics.json means CI has not pushed yet."""
    repo = tmp_path / "ManagementDashboard-data"
    repo.mkdir()
    with pytest.raises(FileNotFoundError) as exc:
        resolve_source(repo)
    assert "metrics.json" in str(exc.value)


def test_sync_copies_content_and_creates_the_destination_dir(tmp_path: Path) -> None:
    src = tmp_path / "metrics.json"
    src.write_text(SAMPLE, encoding="utf-8")
    dest = tmp_path / "docs" / "data" / "metrics.json"
    written = sync(src, dest)
    assert dest.read_text(encoding="utf-8") == SAMPLE
    assert written == len(SAMPLE.encode("utf-8"))


def test_sync_overwrites_an_existing_stale_file(tmp_path: Path) -> None:
    src = tmp_path / "metrics.json"
    src.write_text(SAMPLE, encoding="utf-8")
    dest = tmp_path / "docs" / "data" / "metrics.json"
    dest.parent.mkdir(parents=True)
    dest.write_text('{"stale": true}', encoding="utf-8")
    sync(src, dest)
    assert dest.read_text(encoding="utf-8") == SAMPLE
