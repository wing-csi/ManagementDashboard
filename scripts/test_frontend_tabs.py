"""Tab navigation behaviour.

Panels are hidden, never removed — every render module writes to ids that must
stay resolvable while their panel is off-screen. These tests pin that, plus
ARIA state, keyboard navigation, hash deep-linking, and the Chart.js resize
that a canvas laid out inside a hidden panel would otherwise miss.

Run:  python -m pytest scripts/test_frontend_tabs.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="tab tests need pytest-playwright")

from playwright.sync_api import expect  # noqa: E402  (must follow importorskip)

TABS = ["overview", "quality", "projects", "tasks"]


def open_dashboard(page, server, query: str = "?demo=1"):
    page.goto(f"{server}/{query}", wait_until="networkidle")
    page.wait_for_selector("#taskRows tr", state="attached")
    return page


def visible_panels(page) -> list[str]:
    return [t for t in TABS if page.is_visible(f"#panel-{t}")]


def test_overview_is_the_default_tab(page, server):
    open_dashboard(page, server)
    assert visible_panels(page) == ["overview"]
    assert page.get_attribute("#tab-overview", "aria-selected") == "true"
    assert page.get_attribute("#tab-quality", "aria-selected") == "false"


def test_hidden_panels_still_render_their_content(page, server):
    """The load-bearing constraint: renderers write to hidden panels fine."""
    open_dashboard(page, server)
    assert page.text_content("#taskRows").strip()
    assert page.text_content("#projChips").strip()
    assert page.text_content("#qRework").strip()


def test_clicking_switches_panels(page, server):
    open_dashboard(page, server)
    page.click("#tab-quality")
    assert visible_panels(page) == ["quality"]
    assert page.get_attribute("#tab-quality", "aria-selected") == "true"


def test_hash_deep_links_to_a_tab(page, server):
    open_dashboard(page, server, "?demo=1#quality")
    assert visible_panels(page) == ["quality"]


def test_unknown_hash_falls_back_to_overview(page, server):
    open_dashboard(page, server, "?demo=1#nonsense")
    assert visible_panels(page) == ["overview"]


def test_clicking_a_tab_updates_the_hash(page, server):
    open_dashboard(page, server)
    page.click("#tab-projects")
    assert page.evaluate("() => location.hash") == "#projects"


def test_arrow_keys_move_between_tabs(page, server):
    open_dashboard(page, server)
    page.focus("#tab-overview")
    page.keyboard.press("ArrowRight")
    assert visible_panels(page) == ["quality"]
    page.keyboard.press("ArrowLeft")
    assert visible_panels(page) == ["overview"]
    page.keyboard.press("End")
    assert visible_panels(page) == ["tasks"]
    page.keyboard.press("Home")
    assert visible_panels(page) == ["overview"]


def test_filter_change_preserves_the_active_tab(page, server):
    open_dashboard(page, server)
    page.click("#tab-quality")
    page.select_option("#windowSel", "30")
    assert visible_panels(page) == ["quality"]


def test_chart_recovers_size_after_returning_to_overview(page, server):
    """A canvas laid out while hidden measures 0x0 — tab:shown must resize it."""
    open_dashboard(page, server, "?demo=1#quality")
    page.click("#tab-overview")
    width = page.eval_on_selector("#weeklyChart", "el => el.getBoundingClientRect().width")
    assert width > 0


def open_tasks_tab(page, server):
    open_dashboard(page, server)
    page.click("#tab-tasks")
    return page


def test_table_pages_at_25_rows(page, server):
    open_tasks_tab(page, server)
    expect(page.locator("#taskRows tr")).to_have_count(25)
    assert "25 /" in page.text_content("#tableCap")


def test_load_more_appends_a_page(page, server):
    open_tasks_tab(page, server)
    page.click("#tableMore")
    expect(page.locator("#taskRows tr")).to_have_count(50)


def test_search_filters_rows(page, server):
    open_tasks_tab(page, server)
    page.fill("#taskSearch", "webhook")
    # debounced 150ms — expect() polls, so no fixed sleep
    expect(page.locator("#taskRows tr")).not_to_have_count(25)
    titles = page.eval_on_selector_all(
        "#taskRows tr td:nth-child(6)", "els => els.map(e => e.textContent.toLowerCase())")
    assert titles and all("webhook" in t for t in titles)


def test_level_filter_shows_only_that_level(page, server):
    open_tasks_tab(page, server)
    page.click('#levelFilter [data-level="L4"]')
    levels = page.eval_on_selector_all(
        "#taskRows tr td.lvlcell", "els => els.map(e => e.textContent.trim())")
    assert levels and all(t.startswith("L4") for t in levels)


def test_redline_filter_shows_only_redline_tasks(page, server):
    open_tasks_tab(page, server)
    page.click('#statusFilter [data-status="redline"]')
    rows = page.locator("#taskRows tr")
    expect(rows).to_have_count(25)
    assert rows.locator(".vflag.is-red").count() == rows.count()
    assert page.get_attribute(
        '#statusFilter [data-status="redline"]', "aria-pressed") == "true"
    assert page.get_attribute(
        '#statusFilter [data-status="all"]', "aria-pressed") == "false"


def test_governance_warning_is_distinct_from_a_redline(page, server):
    open_tasks_tab(page, server)
    page.click('#statusFilter [data-status="warning"]')
    rows = page.locator("#taskRows tr")
    expect(rows).to_have_count(2)
    assert rows.locator(".vflag.is-warning").count() == rows.count()
    assert rows.locator(".vflag.is-red").count() == 0


def test_status_and_level_filters_combine(page, server):
    open_tasks_tab(page, server)
    page.click('#statusFilter [data-status="redline"]')
    page.click('#levelFilter [data-level="L3"]')
    rows = page.locator("#taskRows tr")
    assert rows.count() > 0
    assert rows.locator(".vflag.is-red").count() == rows.count()
    levels = page.eval_on_selector_all(
        "#taskRows tr td.lvlcell", "els => els.map(e => e.textContent.trim())")
    assert all(t.startswith("L3") for t in levels)


def test_status_filter_resets_paging(page, server):
    open_tasks_tab(page, server)
    page.click("#tableMore")
    expect(page.locator("#taskRows tr")).to_have_count(50)
    page.click('#statusFilter [data-status="redline"]')
    rows = page.locator("#taskRows tr")
    expect(rows).to_have_count(25)
    assert rows.locator(".vflag.is-red").count() == rows.count()
    assert page.is_visible("#tableMore")


def test_search_resets_paging(page, server):
    """A narrowed result set must not keep the old page offset."""
    open_tasks_tab(page, server)
    page.click("#tableMore")
    expect(page.locator("#taskRows tr")).to_have_count(50)
    page.fill("#taskSearch", "fix")
    expect(page.locator("#taskRows tr")).to_have_count(25)


def test_load_more_hides_when_everything_is_shown(page, server):
    open_tasks_tab(page, server)
    page.click('#levelFilter [data-level="L5"]')
    assert page.is_hidden("#tableMore")


def test_owner_param_and_tab_hash_coexist(page, server):
    """Hash is view state, ?owner= is data state — neither may clobber the other.

    The name must be one the demo dataset actually knows ('wing', lowercase):
    ?owner= is untrusted input, so main.js drops any value that does not match a
    known person and syncOwnerParam() then strips it from the URL.
    """
    open_dashboard(page, server, "?demo=1&owner=wing#quality")
    assert visible_panels(page) == ["quality"]
    assert "owner=wing" in page.evaluate("() => location.search")
    assert page.evaluate("() => location.hash") == "#quality"
