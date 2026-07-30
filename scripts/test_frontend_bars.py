"""Every .bar-fill must actually paint.

Regression guard for a defect that shipped unnoticed: .bar-fill is emitted as
a bare <span> carrying an inline width, and width/height do not apply to
non-replaced inline elements. Every bar in the dashboard rendered at 0x0 —
the 自動化水平分佈 legend, 各 Level 修復佔比, 項目完成度, milestone progress,
and all three Repo 概覽 bar groups. .bar-track escaped only by accident: it is
a grid item, so it gets blockified.

Run:  python -m pytest scripts/test_frontend_bars.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="bar rendering tests need pytest-playwright")

# Reports every .bar-fill the renderers gave a non-zero width, so a bar that is
# legitimately empty (a level with no tasks) cannot mask a collapsed one.
PROBE = """() => {
  return [...document.querySelectorAll('.bar-fill')]
    .map((el) => ({
      width: el.style.width,
      box: el.getBoundingClientRect().width,
      where: el.closest('[id]') ? el.closest('[id]').id : '?',
    }))
    .filter((b) => parseFloat(b.width) > 0);
}"""


def test_bar_fills_have_non_zero_width(page, server):
    """A .bar-fill with a non-zero inline width must occupy non-zero space."""
    page.goto(f"{server}/?demo=1", wait_until="networkidle")
    page.wait_for_selector(".bar-fill", state="attached")

    bars = page.evaluate(PROBE)
    assert bars, "no .bar-fill carried a non-zero inline width — the probe is not exercising anything"

    collapsed = [b for b in bars if b["box"] == 0]
    assert not collapsed, (
        f"{len(collapsed)}/{len(bars)} bar fills rendered at zero width, e.g. {collapsed[:3]}"
    )
