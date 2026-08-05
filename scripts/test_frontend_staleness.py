"""數據過期提示條嘅渲染守則。

Fixture 個日期由 Python 相對「而家」計出嚟,唔係寫死 —— 寫死嘅話呢個檔自己就會
變成下一個「今日過、聽日紅」嘅計時炸彈,正正係整份設計要避開嗰樣嘢。

Run:  python -m pytest scripts/test_frontend_staleness.py -v
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("pytest_playwright",
                    reason="staleness rendering tests need pytest-playwright")

FIXTURE = Path(__file__).parent / "fixtures" / "metrics-fixture.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _ago(**kw) -> str:
    """相對而家嘅 ISO 時間戳。正數 = 幾耐之前。"""
    stamp = datetime.now(timezone.utc) - timedelta(**kw)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _serve(page, data: dict) -> None:
    page.route(
        "**/data/metrics.json",
        lambda route: route.fulfill(
            status=200, content_type="application/json",
            body=json.dumps(data, ensure_ascii=False)),
    )


def _open(page, server):
    page.goto(f"{server}/", wait_until="networkidle")
    page.wait_for_selector("#taskRows tr", state="attached")
    return page


def _with_stamp(stamp: str) -> dict:
    data = _load()
    data["generated_at"] = stamp
    return data


def test_five_day_old_data_raises_the_banner(page, server):
    _serve(page, _with_stamp(_ago(days=5)))
    dash = _open(page, server)
    dash.wait_for_selector("#staleBanner", state="visible")
    assert "5 日前" in dash.inner_text("#staleBanner")


def test_this_mornings_data_raises_nothing(page, server):
    """20 個鐘大係正常。喺度嘈嘅話,真係停咗嗰日就冇人會信呢條 banner。"""
    _serve(page, _with_stamp(_ago(hours=20)))
    dash = _open(page, server)
    dash.wait_for_selector("#taskRows tr", state="attached")
    assert dash.is_hidden("#staleBanner")


def test_demo_mode_never_raises_the_banner(page, server):
    """Demo 數據個 generated_at 死咗喺 2026-07-06,永遠過期。喺度長期掛住一條
    banner,只會訓練啲人當佢透明。"""
    page.goto(f"{server}/?demo=1", wait_until="networkidle")
    page.wait_for_selector("#demoBadge.on", state="attached")
    assert page.is_hidden("#staleBanner")


def test_the_banner_is_announced_politely(page, server):
    _serve(page, _with_stamp(_ago(days=5)))
    dash = _open(page, server)
    dash.wait_for_selector("#staleBanner", state="visible")
    assert dash.get_attribute("#staleBanner", "role") == "status"


def test_a_broken_timestamp_says_so_instead_of_guessing_an_age(page, server):
    _serve(page, _with_stamp("唔係一個日期"))
    dash = _open(page, server)
    dash.wait_for_selector("#staleBanner", state="visible")
    text = dash.inner_text("#staleBanner")
    assert "讀唔到" in text
    assert "日前" not in text


def test_a_future_timestamp_blames_the_clock_not_the_data(page, server):
    stamp = (datetime.now(timezone.utc)
             + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    _serve(page, _with_stamp(stamp))
    dash = _open(page, server)
    dash.wait_for_selector("#staleBanner", state="visible")
    assert "時間唔啱" in dash.inner_text("#staleBanner")


def test_the_banner_cannot_be_dismissed(page, server):
    """撳得走嘅提示一定俾人撳走,撳走就返返去「睇唔見」—— 即係原本要修嗰個問題。"""
    _serve(page, _with_stamp(_ago(days=5)))
    dash = _open(page, server)
    dash.wait_for_selector("#staleBanner", state="visible")
    assert dash.eval_on_selector_all(
        "#staleBanner button, #staleBanner [role=button]", "els => els.length") == 0


def test_the_banner_does_not_overflow_the_narrowest_supported_width(page, server):
    """test_no_horizontal_overflow_at_supported_widths
    (scripts/test_frontend_typography.py:33,63,180) 成日用 ?demo=1 開,而
    demo 模式嘅 banner 一定唔會出 —— 嗰條 test 淨係查緊 375px,但從未真係
    量過呢個 element。呢度攞返同一個闊度,但行真數據(stale)路徑,逼
    banner 出咗先至量,先算真正補到嗰個缺口。"""
    page.set_viewport_size({"width": 375, "height": 812})
    _serve(page, _with_stamp(_ago(days=5)))
    dash = _open(page, server)
    dash.wait_for_selector("#staleBanner", state="visible")
    doc_width = dash.evaluate("() => document.documentElement.scrollWidth")
    win_width = dash.evaluate("() => window.innerWidth")
    assert doc_width <= win_width, (
        f"banner overflows at 375px: scrollWidth {doc_width}px > innerWidth {win_width}px")
