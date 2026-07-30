"""Every .bar-fill must actually paint.

Regression guard for a defect that shipped unnoticed: .bar-fill is emitted as
a bare <span> carrying an inline width, and width/height do not apply to
non-replaced inline elements. Every bar in the dashboard rendered at 0x0 —
the 自動化水平分佈 legend, 各 Level 修復佔比, 項目完成度, milestone progress,
and all three Repo 概覽 bar groups. .bar-track escaped only by accident: it is
a grid item, so it gets blockified.

Geometry is only measurable on a visible element, so the probe walks every tab
and measures the panel that is showing. That also proves each panel's bars
survive being rendered while hidden and laid out later.

Run:  python -m pytest scripts/test_frontend_bars.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="bar rendering tests need pytest-playwright")

TABS = ["overview", "quality", "projects", "tasks"]

# Scoped to the visible panel — a hidden ancestor zeroes getBoundingClientRect.
# Only bars the renderers gave a non-zero width are reported, so a legitimately
# empty bar (a level with no tasks) cannot mask a collapsed one.
PROBE = """() => {
  const panel = document.querySelector('[role="tabpanel"]:not([hidden])');
  if (!panel) return [];
  return [...panel.querySelectorAll('.bar-fill')]
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

    measured = []
    for tab in TABS:
        page.click(f"#tab-{tab}")
        measured += page.evaluate(PROBE)

    assert measured, "no .bar-fill carried a non-zero inline width — the probe is not exercising anything"

    collapsed = [b for b in measured if b["box"] == 0]
    assert not collapsed, (
        f"{len(collapsed)}/{len(measured)} bar fills rendered at zero width, e.g. {collapsed[:3]}"
    )


def test_every_panel_with_bars_is_covered(page, server):
    """Pin the probe's reach: a bar group silently vanishing would hide a defect."""
    page.goto(f"{server}/?demo=1", wait_until="networkidle")
    page.wait_for_selector(".bar-fill", state="attached")

    seen = set()
    for tab in TABS:
        page.click(f"#tab-{tab}")
        seen |= {b["where"] for b in page.evaluate(PROBE)}

    assert {"legend", "qLevels", "ovLangs", "ovTypes", "ovMonthly"} <= seen, (
        f"expected bar groups missing from the probe; saw {sorted(seen)}"
    )
