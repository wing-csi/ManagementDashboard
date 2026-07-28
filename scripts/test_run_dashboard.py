"""Tests for scripts/run_dashboard.py.

The demo-critical behaviour is that a failed `git pull` never stops the dashboard
from starting — these tests pin that.

Run:  python3 -m pytest scripts/test_run_dashboard.py -v
"""

from __future__ import annotations

import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run_dashboard import pull_data_repo, serve  # noqa: E402


def _git(*args: str) -> None:
    subprocess.run(["git", *args], capture_output=True, check=True)


def test_pull_reports_skipped_when_the_clone_is_absent(tmp_path: Path) -> None:
    assert "no clone" in pull_data_repo(tmp_path / "nope")


def test_pull_failure_is_reported_not_raised(tmp_path: Path) -> None:
    """A directory that is not a git repo must not crash the launcher."""
    repo = tmp_path / "not-a-repo"
    repo.mkdir()
    outcome = pull_data_repo(repo)
    assert "failed" in outcome
    assert "on disk" in outcome, "the message must tell the user the demo still works"


def test_pull_succeeds_against_a_real_clone(tmp_path: Path) -> None:
    """An up-to-date clone reports success rather than a failure string."""
    origin, clone = tmp_path / "origin", tmp_path / "clone"
    origin.mkdir()
    _git("init", "-q", "-b", "main", str(origin))
    _git("-C", str(origin), "config", "user.email", "t@example.com")
    _git("-C", str(origin), "config", "user.name", "t")
    (origin / "metrics.json").write_text("{}", encoding="utf-8")
    _git("-C", str(origin), "add", "metrics.json")
    _git("-C", str(origin), "commit", "-qm", "init")
    _git("clone", "-q", str(origin), str(clone))
    assert "failed" not in pull_data_repo(clone)


def test_serve_returns_a_server_that_answers_requests(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>ok</h1>", encoding="utf-8")
    httpd = serve(tmp_path, 0)
    try:
        port = httpd.server_address[1]
        with urllib.request.urlopen(f"http://localhost:{port}/index.html", timeout=5) as r:
            assert r.status == 200
            assert b"ok" in r.read()
    finally:
        httpd.shutdown()
        httpd.server_close()
