"""Global CJK sweep — the test that catches strings nobody remembered to extract.

Every other i18n test asserts that a string we *thought* of came out in English.
This one asserts the inverse, and far more valuable, property: that under
``?demo=1&lang=en`` there is no CJK left anywhere on any of the five tabs.

It is only possible to write this cleanly because ``docs/data/demo-data.js`` is
pure ASCII, so nothing data-derived can contribute CJK in demo mode. On live
data the Tasks table legitimately shows Chinese commit titles (they are the
artefact, not UI copy) — which is exactly why the client demo runs on
``?demo=1``.

Run:  python -m pytest scripts/test_frontend_i18n_sweep.py -v
"""

from __future__ import annotations

import re

import pytest

pytest.importorskip("pytest_playwright",
                    reason="frontend i18n sweep needs pytest-playwright")

PANEL_IDS = [
    "panel-overview", "panel-quality", "panel-projects",
    "panel-product", "panel-tasks",
]

# CJK Unified Ideographs plus the Extension A block, CJK symbols/punctuation
# (、。「」・) and the fullwidth forms (（）) that travel with Chinese copy.
# Deliberately excludes ASCII-range punctuation, which English also uses.
CJK_RE = re.compile(r"[　-〿㐀-䶿一-鿿＀-￯]")

# The one legitimate CJK string in English mode: the language switcher shows
# each language in its own name (EN | 繁). That is the universal convention for
# a language switcher and is not translated copy.
ALLOWED_CJK_SELECTOR = "#langToggle"

# `init()` in docs/js/main.js fills #footStamp only after loadData() resolves
# and render() has run, so a non-empty footStamp is a reliable "the page is
# fully rendered" signal.
#
# Do NOT wait on #managementStatus instead: its placeholder in index.html is an
# EN DASH (U+2013), so a naive `textContent !== '-'` comparison against an ASCII
# hyphen is true before rendering even starts and the wait silently does nothing.
RENDERED = (
    "() => { const el = document.getElementById('footStamp');"
    "        return !!el && el.textContent.trim().length > 0; }"
)


def _load(page, server, query):
    page.goto(f"{server}/{query}", wait_until="networkidle")
    page.wait_for_function(RENDERED)
    # The print stylesheet already force-shows every panel. Do the same here:
    # sweeping only the visible tab would let four fifths of the dashboard ship
    # untranslated and still pass.
    page.evaluate(
        "() => document.querySelectorAll('[role=tabpanel]')"
        "        .forEach((p) => p.removeAttribute('hidden'))"
    )
    return page


@pytest.fixture
def english_demo_page(page, server):
    return _load(page, server, "?demo=1&lang=en")


def _own_text(page, root_selector, skip_selector):
    """Return (text, descriptor) for each element's OWN text under a root.

    Reads element-owned text nodes rather than a subtree ``innerText`` so a
    failure names the exact element still rendering Chinese, instead of dumping
    a whole panel and leaving the reader to hunt for it.
    """
    return page.evaluate(
        """
        ({ rootSelector, skipSelector }) => {
          const root = document.querySelector(rootSelector);
          if (!root) return [];
          const out = [];
          const describe = (el) => el.tagName.toLowerCase()
            + (el.id ? '#' + el.id : '')
            + (typeof el.className === 'string' && el.className.trim()
                ? '.' + el.className.trim().split(/\\s+/).join('.') : '');
          const walk = (el) => {
            if (el.closest(skipSelector)) return;
            for (const node of el.childNodes) {
              if (node.nodeType === Node.TEXT_NODE) {
                const text = node.textContent.trim();
                if (text) out.push([text, describe(el)]);
              }
            }
            for (const child of el.children) walk(child);
          };
          walk(root);
          return out;
        }
        """,
        {"rootSelector": root_selector, "skipSelector": skip_selector},
    )


def _user_facing_attrs(page, root_selector, skip_selector):
    """aria-label / placeholder / title are user-facing too, and easy to miss."""
    return page.evaluate(
        """
        ({ rootSelector, skipSelector }) => {
          const root = document.querySelector(rootSelector);
          if (!root) return [];
          const out = [];
          const attrs = ['aria-label', 'placeholder', 'title'];
          for (const el of [root, ...root.querySelectorAll('*')]) {
            if (el.closest(skipSelector)) continue;
            for (const a of attrs) {
              const v = el.getAttribute(a);
              if (v && v.trim()) {
                out.push([v.trim(), el.tagName.toLowerCase()
                  + (el.id ? '#' + el.id : '') + ' [' + a + ']']);
              }
            }
          }
          return out;
        }
        """,
        {"rootSelector": root_selector, "skipSelector": skip_selector},
    )


def _report(found, what):
    offenders = [(text, where) for text, where in found if CJK_RE.search(text)]
    return offenders, (
        f"{what} still renders Chinese in English mode:\n"
        + "\n".join(f"  {where}: {text!r}" for text, where in offenders[:20])
    )


@pytest.mark.parametrize("panel_id", PANEL_IDS)
def test_no_cjk_in_panel_text(english_demo_page, panel_id):
    found = _own_text(english_demo_page, f"#{panel_id}", ALLOWED_CJK_SELECTOR)
    offenders, message = _report(found, panel_id)
    assert not offenders, message


@pytest.mark.parametrize("panel_id", PANEL_IDS)
def test_no_cjk_in_panel_attributes(english_demo_page, panel_id):
    found = _user_facing_attrs(english_demo_page, f"#{panel_id}", ALLOWED_CJK_SELECTOR)
    offenders, message = _report(found, f"{panel_id} attributes")
    assert not offenders, message


def test_no_cjk_in_page_chrome(english_demo_page):
    """Masthead, filters, tab bar, stale banner and footer — outside the panels."""
    skip = f"{ALLOWED_CJK_SELECTOR}, [role=tabpanel]"
    found = (_own_text(english_demo_page, "body", skip)
             + _user_facing_attrs(english_demo_page, "body", skip))
    offenders, message = _report(found, "Page chrome")
    assert not offenders, message


def test_document_title_is_english(english_demo_page):
    title = english_demo_page.title()
    assert not CJK_RE.search(title), f"<title> is still Chinese: {title!r}"


def test_language_toggle_is_the_only_allowed_cjk(english_demo_page):
    """Guard the allowlist itself.

    If the toggle ever stops containing CJK, this exemption is silently covering
    nothing — and a real regression could later hide behind it unnoticed.
    """
    toggle = english_demo_page.locator(ALLOWED_CJK_SELECTOR).inner_text()
    assert CJK_RE.search(toggle), (
        f"{ALLOWED_CJK_SELECTOR} no longer contains CJK, so the sweep's allowlist "
        "is dead weight hiding nothing — remove the exemption or restore the 繁 label."
    )


def test_chinese_mode_still_renders_chinese(page, server):
    """The override contract: with no lang param, nothing here changed.

    Without this, a bug that translated everything unconditionally would make
    every assertion above pass while silently breaking the default experience.
    """
    _load(page, server, "?demo=1")
    body = page.locator("body").inner_text()
    assert CJK_RE.search(body), "Default (no ?lang=) must still render Chinese"
