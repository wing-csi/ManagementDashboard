"""Typography scale and layout-overflow regression tests.

Two things are pinned here.

**The type scale.** dashboard.css carried 19 distinct font sizes across 79
declarations, and 9 of those sizes were ≤13.5px separated by 0.5px steps — a
step that small carries no hierarchy, so nine numbers were doing one number's
job. The floor was 9px (`thead th .arrow`) with 10px on `.hero-tag`,
`.dora-lead` and `.typechip`. Contrast passed WCAG AA at every one of those
sizes, which said nothing useful: AA sets no minimum text size. On a dashboard
read by management, 10px is too small whatever the contrast ratio.

**Horizontal overflow.** Raising the floor reflows the densest text in the
page — table headers, chips, card notes. The redesign commit recorded a manual
check at 1440 / 900 / 375px but committed no test, so nothing would have caught
a regression. These run in pytest-playwright's own headless Chromium, which
measures layout accurately, and they are the safety net for the scale change.

Run:  python -m pytest scripts/test_frontend_typography.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="typography tests need pytest-playwright")

#: Floor for any text a reader is expected to read.
MIN_FONT_PX = 12

#: The three widths the layout redesign claimed to support.
WIDTHS = [(1440, 900), (900, 1000), (375, 812)]

_VISIBLE_TEXT_SIZES = """
() => {
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    if (!el.offsetParent && el.tagName !== 'BODY') continue;
    const owns = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!owns) continue;
    out.push({
      size: parseFloat(getComputedStyle(el).fontSize),
      cls: (el.className || el.tagName).toString().slice(0, 40),
      text: el.textContent.trim().slice(0, 30),
    });
  }
  return out;
}
"""


def parse_px(value: str) -> float:
    return float(value.replace("px", "").strip())


def open_all_panels(page, server):
    """Load the dashboard and reveal every tab panel.

    Panels are hidden until selected, and hidden elements have no offsetParent,
    so a single-tab probe would silently skip most of the page.
    """
    page.goto(f"{server}/?demo=1", wait_until="networkidle")
    page.wait_for_selector("#taskRows tr", state="attached")
    page.evaluate("() => document.querySelectorAll('[role=tabpanel]')"
                  ".forEach(p => p.hidden = false)")
    return page


# ------------------------------ the floor ------------------------------

def test_no_visible_text_is_smaller_than_the_floor(page, server):
    dash = open_all_panels(page, server)
    tiny = [r for r in dash.evaluate(_VISIBLE_TEXT_SIZES) if r["size"] < MIN_FONT_PX]
    assert not tiny, (
        f"{len(tiny)} element(s) render below {MIN_FONT_PX}px: "
        + "; ".join(f'{t["size"]}px {t["cls"]} :: {t["text"]}' for t in tiny[:8])
    )


# ------------------------------ the scale ------------------------------

def test_the_body_scale_has_few_enough_steps_to_read_as_a_hierarchy(page, server):
    """Sizes below 20px are the body tier. Nine near-identical steps there is
    what the tokens replaced; allowing more than five would let them back."""
    dash = open_all_panels(page, server)
    body_tier = {r["size"] for r in dash.evaluate(_VISIBLE_TEXT_SIZES) if r["size"] < 20}
    assert len(body_tier) <= 5, (
        f"body tier has {len(body_tier)} distinct sizes: {sorted(body_tier)}")


def test_body_scale_steps_are_perceptible(page, server):
    """A 0.5px step is below the threshold at which a reader sees a difference,
    so it creates no hierarchy while still costing a number to maintain."""
    dash = open_all_panels(page, server)
    steps = sorted({r["size"] for r in dash.evaluate(_VISIBLE_TEXT_SIZES) if r["size"] < 20})
    too_close = [(a, b) for a, b in zip(steps, steps[1:]) if b - a < 1.5]
    assert not too_close, f"steps closer than 1.5px: {too_close}"


def test_the_scale_comes_from_tokens_not_scattered_literals(page, server):
    """The tokens are the single place the scale is defined. If they vanish,
    the 0.5px sprawl can come back one declaration at a time."""
    dash = open_all_panels(page, server)
    tokens = dash.evaluate(
        "() => ['--fs-xs','--fs-sm','--fs-md','--fs-lg','--fs-xl']"
        ".map(t => getComputedStyle(document.documentElement).getPropertyValue(t).trim())")
    assert all(tokens), f"missing type tokens: {tokens}"
    assert parse_px(tokens[0]) >= MIN_FONT_PX, f"--fs-xs is below the floor: {tokens[0]}"


def test_the_display_tier_is_tokenised_too(page, server):
    """Named by role rather than by step, because these are three jobs and not
    a scale: the hero has to win the page, the KPI values have to win their
    cards, the masthead sits under both."""
    dash = open_all_panels(page, server)
    got = dash.evaluate(
        "() => Object.fromEntries("
        "['--fs-display','--fs-display-sm','--fs-metric','--fs-title']"
        ".map(t => [t, getComputedStyle(document.documentElement)"
        ".getPropertyValue(t).trim()]))")
    assert all(got.values()), f"missing display tokens: {got}"
    assert parse_px(got["--fs-display"]) > parse_px(got["--fs-metric"]) \
        > parse_px(got["--fs-title"]), f"display tier is not ordered: {got}"


def test_no_font_size_literal_survives_outside_the_token_block(page, server):
    """The tokens only hold the line if nothing bypasses them. Inline styles in
    render-table.js and index.html did exactly that before this change — four
    of the seven sat below the 12px floor while the stylesheet looked clean."""
    import re
    from pathlib import Path
    css = Path(__file__).parent.parent / "docs" / "css" / "dashboard.css"
    text = css.read_text(encoding="utf-8")
    after_root = text[text.index("}", text.index(":root {")):]
    strays = re.findall(r"font-size:\s*[\d.]+px", after_root)
    assert not strays, f"literal font-size outside :root — {strays}"

    for rel in ("docs/index.html", "docs/js/render-table.js", "docs/js/render-kpi.js"):
        src = (css.parent.parent.parent / rel).read_text(encoding="utf-8")
        inline = re.findall(r"font-size:\s*[\d.]+px", src)
        assert not inline, f"inline font-size literal in {rel} — {inline}"


# --------------------------- body readability ---------------------------

def test_body_text_is_at_least_15px(page, server):
    """Traditional Chinese carries more stroke density per em than Latin, so
    the same px value reads smaller. 14px Latin passes for 16; 14px 繁中 is
    just 14."""
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    size = page.evaluate("() => parseFloat(getComputedStyle(document.body).fontSize)")
    assert size >= 15, f"body is {size}px"


def test_body_line_height_gives_cjk_room(page, server):
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    ratio = page.evaluate("""() => {
      const c = getComputedStyle(document.body);
      return parseFloat(c.lineHeight) / parseFloat(c.fontSize);
    }""")
    assert ratio >= 1.55, f"body line-height ratio is {ratio:.2f}"


# --------------------------- layout overflow ---------------------------

@pytest.mark.parametrize("width,height", WIDTHS)
def test_no_horizontal_overflow_at_supported_widths(page, server, width, height):
    """The safety net for the scale change: bigger text must not push the page
    sideways. The redesign checked these three widths by hand and committed
    nothing, so a regression had nothing to trip over.

    Measured one tab at a time, which is the only state a reader ever sees.
    open_all_panels() is right for probing type — font-size does not depend on
    layout — but revealing four panels at once stacks content the page never
    stacks, and an overflow measured there would be an artefact of the probe.
    """
    page.set_viewport_size({"width": width, "height": height})
    dash = page
    dash.goto(f"{server}/?demo=1", wait_until="networkidle")
    dash.wait_for_selector("#taskRows tr", state="attached")

    tabs = dash.eval_on_selector_all("[role=tab]", "els => els.map(e => e.id)")
    assert tabs, "no tabs found — the probe would measure nothing"

    overflows = []
    for tab in tabs:
        dash.click(f"#{tab}")
        over = dash.evaluate(
            "() => document.body.scrollWidth - document.documentElement.clientWidth")
        if over > 0:
            overflows.append(f"{tab} +{over}px")
    assert not overflows, f"body overflows at {width}px: {overflows}"
