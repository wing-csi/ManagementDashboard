"""Rendered management summary and data-trust states."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("pytest_playwright", reason="management rendering tests need pytest-playwright")

FIXTURE = Path(__file__).parent / "fixtures" / "metrics-fixture-burndown.json"


def load_data() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def serve(page, data: dict) -> None:
    page.route("**/data/metrics.json", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(data, ensure_ascii=False)))


def open_dashboard(page, server):
    page.goto(f"{server}/", wait_until="networkidle")
    page.wait_for_selector("#managementProjects .management-project", state="attached")
    return page


def test_overview_renders_management_status_scope_and_attention(page, server):
    data = load_data()
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    serve(page, data)
    dash = open_dashboard(page, server)
    assert dash.text_content("#managementStatus").strip() == "Off track"
    assert dash.text_content("#managementHealth").strip() == "Fresh"
    assert dash.text_content("#managementScope").strip() == "12"
    assert dash.locator("#managementAttention li").count() > 0
    assert dash.locator("#managementProjects .management-project").count() == 2


def test_stale_real_data_gets_a_persistent_warning(page, server):
    data = load_data()
    data["generated_at"] = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    serve(page, data)
    dash = open_dashboard(page, server)
    assert dash.is_visible("#staleBanner")
    assert "舊快照" in dash.text_content("#staleBanner")


def test_demo_mode_never_shows_the_stale_warning(page, server):
    page.goto(f"{server}/?demo=1", wait_until="networkidle")
    page.wait_for_selector("#managementStatus")
    assert page.is_hidden("#staleBanner")


def test_issue_collection_failure_is_not_silently_called_no_planning_data(page, server):
    data = load_data()
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    data = deepcopy(data)
    data["repo_meta"]["acme/beta"]["issues_error"] = "Resource not accessible by personal access token"
    serve(page, data)
    dash = open_dashboard(page, server)
    assert dash.text_content("#managementHealth").strip() == "Needs attention"
    assert "收集唔到 Issues" in dash.text_content("#managementAttention")

