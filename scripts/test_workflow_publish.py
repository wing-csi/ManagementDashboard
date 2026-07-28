"""Regression guards for the CI data pipeline.

The original incident: metrics.json (containing private client repo metadata) was
published to public GitHub Pages and committed to a public repo. Phase 0 removed that;
Phase 1 replaces it with a push to a PRIVATE data repo. These tests make it hard to
silently regress into publishing from the public repo again.

Run:  python3 -m pytest scripts/test_workflow_publish.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "collect.yml"
GITIGNORE = ROOT / ".gitignore"
DATA_REPO = "wing-csi/ManagementDashboard-data"
PUBLISH_STEP = "Publish metrics to private data repo"
CHECKOUT_STEP = "Checkout private data repo"


# --- dependency-free guards: these must never skip ---------------------------

def test_metrics_json_stays_gitignored() -> None:
    """The original leak was metrics.json tracked in a public repo. Never again."""
    assert "docs/data/metrics.json" in GITIGNORE.read_text(encoding="utf-8")


def test_workflow_has_no_pages_publishing() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    for forbidden in ("configure-pages", "upload-pages-artifact", "deploy-pages"):
        assert forbidden not in text, f"Pages publishing step {forbidden!r} is back"


def test_collector_writes_outside_the_repo() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "--out /tmp/metrics.json" in text
    assert "--out docs/data/metrics.json" not in text


def test_token_is_never_interpolated_into_a_shell_string() -> None:
    """A token in a URL or echo can leak via set -x, error output, or a crash dump."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "echo ${{ secrets.DATA_REPO_PAT }}" not in text
    assert "x-access-token:${" not in text, "put the PAT in actions/checkout, not a URL"


# --- structural guards: need PyYAML — they skip without it; the file-text guards above never do ---


def _steps() -> list[dict]:
    yaml = pytest.importorskip("yaml", reason="PyYAML needed for workflow structure tests")
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    (job,) = wf["jobs"].values()
    return job["steps"]


def _step(name: str) -> dict:
    for s in _steps():
        if s.get("name") == name:
            return s
    pytest.fail(f"workflow step {name!r} not found")


def test_workflow_token_stays_read_only() -> None:
    """The job pushes with a PAT, so the workflow's own token needs no write access."""
    yaml = pytest.importorskip("yaml", reason="PyYAML needed for workflow structure tests")
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert wf["permissions"] == {"contents": "read"}


def test_data_repo_checkout_targets_the_private_repo() -> None:
    step = _step(CHECKOUT_STEP)
    assert step["with"]["repository"] == DATA_REPO
    assert step["with"]["token"] == "${{ secrets.DATA_REPO_PAT }}"
    assert step["with"]["path"] == "data-repo"


def test_publish_steps_are_guarded_against_pull_requests() -> None:
    """Fork PRs cannot read secrets; an unguarded push step fails on every PR."""
    guard = "github.event_name != 'pull_request'"
    for name in (CHECKOUT_STEP, PUBLISH_STEP):
        assert guard in _step(name)["if"], f"{name} is missing the pull_request guard"


def test_publish_step_pushes_from_the_data_repo_only() -> None:
    step = _step(PUBLISH_STEP)
    assert step["working-directory"] == "data-repo"
    assert "git push" in step["run"]
