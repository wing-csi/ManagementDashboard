"""i18n coverage for the burndown cards and the plan timeline strip
(Track C: render-burndown.js + render-timeline.js).

Every string these two modules render now goes through `t()`. This suite
checks the English extraction landed correctly and, critically, that the
Chinese path is untouched byte-for-byte — scripts/test_frontend_burndown.py
and scripts/test_frontend_timeline.py are the real pin for that and must
stay green; this file adds the English-side assertions plus the one
behaviour change (the date-format disambiguation) that those two files
cannot cover.

Run:  python -m pytest scripts/test_frontend_i18n_burndown.py -v
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("pytest_playwright",
                    reason="i18n burndown/timeline tests need pytest-playwright")

FIXTURE = Path(__file__).parent / "fixtures" / "metrics-fixture-burndown.json"

# A bare NN/NN date is ambiguous in English (8 June vs 6 August) — the one
# thing this suite must prove is gone from the English render.
BARE_SLASH_DATE_RE = re.compile(r"(?<!\d)\d{2}/\d{2}(?!\d)")
MONTH_NAME_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b")


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _serve(page, data: dict) -> None:
    page.route(
        "**/data/metrics.json",
        lambda route: route.fulfill(
            status=200, content_type="application/json",
            body=json.dumps(data, ensure_ascii=False)),
    )


def _open(page, server, query: str = "") -> object:
    page.goto(f"{server}/{query}", wait_until="networkidle")
    page.wait_for_selector("#taskRows tr", state="attached")
    return page


def _metrics_text(page) -> list[str]:
    page.wait_for_selector("#burndownCards .burn-metric", state="attached")
    return page.locator("#burndownCards .burn-metric").evaluate_all(
        "els => els.map(el => el.textContent.replace(/\\s+/g, ' ').trim())")


def _card_text(page, server, data: dict, query: str) -> str:
    _serve(page, data)
    dash = _open(page, server, query)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    return dash.inner_text("#burndownCards")


# --------------------------- the date-format fix ---------------------------

def test_default_chinese_target_date_is_the_exact_slash_format(page, server):
    """No `lang` param — override contract: byte-identical to pre-i18n zh."""
    _serve(page, _load())
    dash = _open(page, server)
    metrics = _metrics_text(dash)
    assert "目標日 08/06 剩 2 日" in metrics


def test_chinese_lang_param_still_uses_the_slash_format(page, server):
    _serve(page, _load())
    dash = _open(page, server, "?lang=zh")
    metrics = _metrics_text(dash)
    assert "目標日 08/06 剩 2 日" in metrics


def test_english_target_date_spells_out_the_month(page, server):
    """due_max is 2026-08-06 — ambiguous as '08/06', unambiguous as '06 Aug'."""
    _serve(page, _load())
    dash = _open(page, server, "?lang=en")
    metrics = _metrics_text(dash)
    target = next((m for m in metrics if m.startswith("Target date")), None)
    assert target is not None, f"no Target date metric among {metrics}"
    assert MONTH_NAME_RE.search(target), f"no month name in {target!r}"
    assert not BARE_SLASH_DATE_RE.search(target), f"still ambiguous: {target!r}"
    assert "06 Aug" in target


def test_english_forecast_date_also_spells_out_the_month(page, server):
    """Every shortDate() call site benefits, not just the target-date metric."""
    data = _load()
    plan = data["repo_meta"]["acme/alpha"]["plan"]
    plan.update(done=4, total=10, due_max="2026-08-10")
    plan["history"] = [
        {"date": "2026-07-20", "done": 0, "total": 10},
        {"date": "2026-07-27", "done": 2, "total": 10},
        {"date": "2026-08-03", "done": 4, "total": 10},
    ]
    _serve(page, data)
    dash = _open(page, server, "?lang=en")
    metrics = _metrics_text(dash)
    forecast = next((m for m in metrics if m.startswith("Forecast completion")), None)
    assert forecast is not None, f"no Forecast completion metric among {metrics}"
    assert MONTH_NAME_RE.search(forecast), f"no month name in {forecast!r}"
    assert not BARE_SLASH_DATE_RE.search(forecast), f"still ambiguous: {forecast!r}"


# ------------------------------ metric labels ------------------------------

def test_burndown_metric_labels_are_english(page, server):
    _serve(page, _load())
    dash = _open(page, server, "?lang=en")
    metrics = _metrics_text(dash)
    labels = [m.split(" ")[0] for m in metrics]
    text = " | ".join(metrics)
    assert "Completion" in text
    assert "Remaining work" in text
    assert any(m.startswith("Target date") for m in metrics)
    assert any(m.startswith("Scope change") for m in metrics)
    assert any(m.startswith("Forecast completion") for m in metrics)
    assert labels  # sanity: metrics were actually found


def test_burndown_headline_status_and_gap_are_english(page, server):
    _serve(page, _load())
    dash = _open(page, server, "?lang=en")
    text = dash.inner_text("#burndownCards")
    assert "Off track" in text
    assert "Actual progress is 35 pp behind today's plan" in text


# ------------------------- "no ideal line" reasons -------------------------

def test_no_ideal_line_reason_when_plan_has_no_due(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["due_max"] = None
    text = _card_text(page, server, data, "?lang=en")
    assert "no ideal line" in text
    assert "plan.md has no due:" in text


def test_no_ideal_line_reason_when_due_is_not_a_calendar_date(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["due_max"] = "2026-13-01"
    text = _card_text(page, server, data, "?lang=en")
    assert "no ideal line" in text
    assert "is not a valid date" in text


def test_no_ideal_line_reason_when_due_is_not_after_start(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["due_max"] = "2026-07-01"
    text = _card_text(page, server, data, "?lang=en")
    assert "no ideal line can be drawn" in text
    # distinguishable from the "no due:" reason, same as the zh assertion in
    # test_frontend_burndown.py
    assert "plan.md has no due:" not in text


# --------------------------------- SPI bands --------------------------------

def test_spi_band_label_is_english(page, server):
    _serve(page, _load())
    dash = _open(page, server, "?lang=en")
    head = dash.inner_text("#burndownCards .tl-head")
    assert "SPI 0.42" in head
    assert "Seriously behind" in head


def test_spi_days_left_and_overdue_count_interpolate_in_english(page, server):
    _serve(page, _load())
    dash = _open(page, server, "?lang=en")
    head = dash.inner_text("#burndownCards .tl-head")
    assert "2 d left" in head
    assert "2 tasks overdue" in head


# ------------------------------ NO_SPI reasons ------------------------------

def test_no_spi_reason_for_an_unusable_due_date_in_english(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["due_max"] = "2026-02-30"
    _serve(page, data)
    dash = _open(page, server, "?lang=en")
    dash.wait_for_selector("#burndownCards .tl", state="attached")
    head = dash.inner_text("#burndownCards .tl-head")
    assert "not a valid date" in head
    assert "no SPI" in head
    assert "SPI 0." not in head
    assert not any(band in head for band in
                    ("Keeping up", "Behind", "Seriously behind"))


def test_no_spi_reason_when_plan_has_no_due_in_english(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["due_max"] = None
    _serve(page, data)
    dash = _open(page, server, "?lang=en")
    dash.wait_for_selector("#burndownCards .tl", state="attached")
    head = dash.inner_text("#burndownCards .tl-head")
    assert "plan.md has no due:" in head
    assert "no SPI" in head


# --------------------------- timeline note (Chinese) ------------------------

def test_chinese_timeline_note_and_marker_count_are_unchanged(page, server):
    """Byte-identical guard for the timeline strip's own Chinese assertions
    (test_frontend_timeline.py owns the full list; this is a smoke check)."""
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl-head", state="attached")
    head = dash.inner_text("#burndownCards .tl-head")
    assert "SPI 0.42" in head
    assert "嚴重落後" in head
    assert "剩 2 日" in head
    assert "2 項工作過咗期" in head


def test_english_timeline_note_mentions_unfinished_work(page, server):
    _serve(page, _load())
    dash = _open(page, server, "?lang=en")
    dash.wait_for_selector("#burndownCards .tl", state="attached")
    text = dash.inner_text("#burndownCards .tl")
    assert "only shows unfinished work" in text


def test_english_invalid_task_due_count_interpolates(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["open_tasks"].append(
        {"title": "P-99 bad date", "due": "2026-02-30", "priority": "P2",
         "bug": False, "section": "Phase 2"})
    _serve(page, data)
    dash = _open(page, server, "?lang=en")
    dash.wait_for_selector("#burndownCards .tl", state="attached")
    text = dash.inner_text("#burndownCards .tl")
    assert "1 task's due:" in text
