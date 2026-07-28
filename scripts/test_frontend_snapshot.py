"""Rendered-output snapshot test for docs/index.html.

Proves the Phase 0 frontend split is behaviour-preserving. Regenerate the
baseline deliberately with:  pytest scripts/test_frontend_snapshot.py --snapshot-update

Run:  python3 -m pytest scripts/test_frontend_snapshot.py -v
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

# pytest-playwright is what supplies the `page` fixture. Guarding on the bare
# `playwright` package let a machine with playwright-but-not-pytest-playwright
# fail collection with "fixture 'page' not found" instead of skipping cleanly.
pytest.importorskip("pytest_playwright",
                    reason="frontend snapshot test needs pytest-playwright")

DOCS = Path(__file__).parent.parent / "docs"
FIXTURES = Path(__file__).parent / "fixtures"
BASELINE = FIXTURES / "rendered-baseline.json"

# NOTE: the milestones section id in docs/index.html is "projMilestones",
# not "projMs" — verified against docs/index.html before writing this list.
SECTION_IDS = [
    "strip", "alertList", "taskRows", "projChips", "projMilestones",
    "projLate", "projTodo", "footStamp",
]


# The `server` fixture lives in scripts/conftest.py — several frontend test
# modules need it, and one shared read-only http.server is enough for all.


@pytest.fixture(scope="module")
def fixture_data():
    """Swap the fixture in as docs/data/metrics.json for the duration of the test.

    Setup and yield are wrapped in try/finally so the real file is always
    restored on the way out — even if a disk-full or permission error
    strikes between the backup move and the fixture copy landing — instead
    of relying on `yield` being reached for teardown to run.
    """
    target = DOCS / "data" / "metrics.json"
    backup = DOCS / "data" / "metrics.json.snapshot-backup"
    had_original = target.exists()
    try:
        if had_original:
            shutil.move(target, backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIXTURES / "metrics-fixture.json", target)
        yield
    finally:
        if had_original:
            if backup.exists():
                shutil.move(backup, target)
        else:
            target.unlink(missing_ok=True)


def render_sections(page) -> dict[str, str]:
    return {
        sid: page.eval_on_selector(f"#{sid}", "el => el.innerHTML")
        for sid in SECTION_IDS
    }


def test_rendered_output_matches_baseline(page, server, fixture_data, request):
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#taskRows tr", timeout=10_000)
    actual = render_sections(page)

    for sid in SECTION_IDS:
        assert actual[sid].strip(), f"section #{sid} rendered empty"

    if request.config.getoption("--snapshot-update") or not BASELINE.exists():
        BASELINE.write_text(json.dumps(actual, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
        pytest.skip("baseline written")

    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    for sid in SECTION_IDS:
        assert actual[sid] == expected[sid], f"rendered output changed for #{sid}"


def test_missing_data_shows_error_not_demo(page, server, fixture_data):
    """A failed data fetch must show an explicit error, never silent demo data."""
    page.route("**/data/metrics.json", lambda route: route.fulfill(status=500))
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#loadError", state="visible", timeout=10_000)
    assert page.is_visible("#loadError")


def test_demo_mode_is_explicit(page, server, fixture_data):
    """?demo=1 still loads the demo dataset deliberately."""
    page.goto(f"{server}/?demo=1", wait_until="networkidle")
    page.wait_for_selector("#demoBadge", timeout=10_000)
    assert page.is_visible("#demoBadge")
