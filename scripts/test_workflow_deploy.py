"""Guards for the Cloudflare Pages deploy step added in Phase 2.

Phase 2 hosts the dashboard (including the private metrics.json) on Cloudflare
Pages behind Cloudflare Access. These tests pin the safety properties of the
deploy step: fail loudly when secrets are missing, never leak the token into a
shell string, never commit metrics.json, and only deploy after the data-repo
publish has completed.

Run:  python3 -m pytest scripts/test_workflow_deploy.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "collect.yml"
DEPLOY_STEP = "Deploy dashboard to Cloudflare Pages"
PUBLISH_STEP = "Publish metrics to private data repo"
COLLECT_STEP = "Collect metrics"


# --- dependency-free guards: these must never skip ---------------------------

def test_deploy_uses_pinned_wrangler_and_exact_project() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "wrangler@4 pages deploy docs" in text
    assert "--project-name=management-dashboard" in text
    assert "--branch=main" in text


def test_deploy_token_is_never_interpolated_into_a_shell_string() -> None:
    """The token must reach wrangler via env:, not inline ${{ }} in run lines."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "echo ${{ secrets.CLOUDFLARE_API_TOKEN }}" not in text
    for line in text.splitlines():
        if "wrangler" in line:
            assert "${{" not in line, f"secret interpolated into shell line: {line!r}"


# --- structural guards: need PyYAML — they skip without it -------------------

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


def test_deploy_step_is_guarded_against_pull_requests() -> None:
    """Fork PRs cannot read secrets; an unguarded deploy step fails on every PR."""
    assert "github.event_name != 'pull_request'" in _step(DEPLOY_STEP)["if"]


def test_deploy_step_passes_secrets_via_env() -> None:
    env = _step(DEPLOY_STEP)["env"]
    assert env["CLOUDFLARE_API_TOKEN"] == "${{ secrets.CLOUDFLARE_API_TOKEN }}"
    assert env["CLOUDFLARE_ACCOUNT_ID"] == "${{ secrets.CLOUDFLARE_ACCOUNT_ID }}"


def test_deploy_step_fails_loudly_when_secrets_missing() -> None:
    """Spec: missing secrets must be an explicit CI failure, never a silent skip."""
    run = _step(DEPLOY_STEP)["run"]
    assert 'if [ -z "$CLOUDFLARE_API_TOKEN" ]' in run
    assert 'if [ -z "$CLOUDFLARE_ACCOUNT_ID" ]' in run
    assert "exit 1" in run


def test_deploy_copies_metrics_into_the_runner_workspace_only() -> None:
    run = _step(DEPLOY_STEP)["run"]
    assert "cp /tmp/metrics.json docs/data/metrics.json" in run
    assert "git add" not in run, "metrics.json must never be committed to this repo"


def test_deploy_runs_after_the_data_repo_publish() -> None:
    names = [s.get("name") for s in _steps()]
    assert names.index(DEPLOY_STEP) > names.index(PUBLISH_STEP)


# --- the two sinks must fail independently -----------------------------------
#
# Ordering and *conditional dependency* are different things. The test above pins
# the order — deploy last — and that is fine. What follows pins that the order
# does not also make the deploy inherit the data repo's failures.

def test_a_data_repo_failure_does_not_skip_the_cloudflare_deploy() -> None:
    """The design treats the private data repo and Pages as two independent sinks,
    each a fallback for the other. Under GitHub's default `success()` gate they are
    not independent: an expired DATA_REPO_PAT fails the checkout, every later step
    is skipped, and the Pages site quietly keeps serving the previous deploy. The
    run does go red in Actions — but nobody watches Actions, and the dashboard
    itself shows no sign that its numbers are old.

    The design's error-handling section reasoned about the opposite direction only
    ("deploy fails, data-repo publish has already completed"), so this direction
    was never considered.
    """
    cond = _step(DEPLOY_STEP)["if"]
    assert "!cancelled()" in cond, (
        "the deploy inherits the default success() gate, so an earlier failure "
        "silently skips it and the dashboard serves stale data"
    )


def test_the_deploy_still_refuses_to_run_without_a_good_collect() -> None:
    """`!cancelled()` on its own is too permissive — it would also deploy after the
    collector itself crashed, shipping a stale or half-written /tmp/metrics.json as
    though it were today's numbers. Resilience to the data repo must not become
    indifference to the data.
    """
    cond = _step(DEPLOY_STEP)["if"]
    assert "steps.collect.outcome == 'success'" in cond, (
        "the deploy must gate on the collector having succeeded"
    )
    assert _step(COLLECT_STEP).get("id") == "collect", (
        "the deploy's condition references steps.collect, so the collect step "
        "needs that id"
    )
