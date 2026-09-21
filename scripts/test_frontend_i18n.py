"""Tests for the i18n infrastructure (Phase 1a): language resolution, the
`t()` lookup/interpolation/pluralisation core, DOM application, the language
toggle, and URL/localStorage round-tripping.

This is infrastructure only — no UI copy is extracted yet, so every real
dictionary namespace ships empty. `t()` therefore hits its missing-key path
for any real key in this phase; that is expected and is itself asserted
below. Interpolation and pluralisation are unit-tested against a synthetic
dictionary passed straight to the exported `translate()` core, so they do
not depend on any string extraction landing first.

With no `lang` param, output must stay byte-for-byte identical to the
pre-i18n baseline (scripts/fixtures/rendered-baseline.json, pinned by
test_frontend_snapshot.py) — this suite never asserts against that fixture
and must never be run with --snapshot-update.

Run:  python -m pytest scripts/test_frontend_i18n.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="i18n tests need pytest-playwright")

KNOWN_OWNER = "wing"  # present in the ?demo=1 dataset — see test_frontend_tabs.py


def open_dashboard(page, server, query: str = "?demo=1"):
    page.goto(f"{server}/{query}", wait_until="networkidle")
    page.wait_for_selector("#taskRows tr", state="attached")
    return page


def click_language(page, code: str, expected_locale: str):
    """Click a language button and wait for the RELOADED document.

    Deliberately not `page.expect_navigation()`: it resolves on the FIRST
    navigation after the click, and the assertions that follow would then run
    against the document that is on its way out. Waiting on the attribute the
    new document sets is the thing we actually care about, and it does not
    care how the toggle gets there.
    """
    page.click(f'.controls #langToggle .lang-btn[data-lang="{code}"]')
    page.wait_for_function(
        "(locale) => document.documentElement.lang === locale",
        arg=expected_locale,
    )


# --------------------------- default is untouched ---------------------------

def test_default_url_renders_chinese(page, server):
    """No `lang` param — the override contract: output must stay Chinese."""
    open_dashboard(page, server)
    assert page.get_attribute("html", "lang") == "zh-Hant"
    lang = page.evaluate("async () => (await import('/js/i18n/index.js')).LANG")
    assert lang == "zh"


# --------------------------------- ?lang=en ---------------------------------

def test_lang_en_param_flips_html_lang(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    assert page.get_attribute("html", "lang") == "en"
    lang = page.evaluate("async () => (await import('/js/i18n/index.js')).LANG")
    assert lang == "en"


def test_unsupported_lang_param_falls_back_to_zh(page, server):
    """Only 'zh' and 'en' are accepted — anything else falls through."""
    open_dashboard(page, server, "?demo=1&lang=fr")
    assert page.get_attribute("html", "lang") == "zh-Hant"


# ------------------------------ the toggle UI ------------------------------

def test_language_toggle_is_present_in_controls_and_is_not_a_select(page, server):
    open_dashboard(page, server)
    toggle = page.query_selector(".controls #langToggle")
    assert toggle is not None, "no #langToggle found inside .controls"
    assert toggle.evaluate("el => el.tagName").lower() != "select"
    assert page.query_selector(".controls #langToggle select") is None


def test_toggle_mounts_after_stamp(page, server):
    """Mounted as the LAST child of .controls, after #stamp."""
    open_dashboard(page, server)
    last_id = page.eval_on_selector(".controls", "el => el.lastElementChild.id")
    assert last_id == "langToggle"


def test_toggle_buttons_reflect_active_language(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    pressed = page.eval_on_selector_all(
        ".controls #langToggle .lang-btn",
        "els => els.map(e => [e.dataset.lang, e.getAttribute('aria-pressed')])",
    )
    assert ["en", "true"] in pressed
    assert ["zh", "false"] in pressed


# ------------------------- owner + hash round-trip -------------------------

def test_owner_and_hash_survive_tab_switch_with_lang_en(page, server):
    open_dashboard(page, server, f"?demo=1&lang=en&owner={KNOWN_OWNER}#quality")
    assert page.evaluate("() => location.hash") == "#quality"
    assert f"owner={KNOWN_OWNER}" in page.evaluate("() => location.search")

    page.click("#tab-projects")
    assert page.evaluate("() => location.hash") == "#projects"
    assert f"owner={KNOWN_OWNER}" in page.evaluate("() => location.search")
    assert "lang=en" in page.evaluate("() => location.search")


def test_owner_and_hash_survive_toggling_language(page, server):
    open_dashboard(page, server, f"?demo=1&lang=en&owner={KNOWN_OWNER}#quality")
    click_language(page, "zh", "zh-Hant")
    assert page.evaluate("() => location.hash") == "#quality"
    assert f"owner={KNOWN_OWNER}" in page.evaluate("() => location.search")
    assert page.get_attribute("html", "lang") == "zh-Hant"


# ------------------------------ t() unit tests ------------------------------

def import_i18n(page, server):
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")


def test_translate_interpolates_named_placeholders(page, server):
    import_i18n(page, server)
    got = page.evaluate("""
        async () => {
          const m = await import('/js/i18n/index.js');
          const dict = { en: { misc: { greet: 'Hello, {name}!' } } };
          return m.translate(dict, 'en', 'misc.greet', { name: 'Wing' });
        }
    """)
    assert got == "Hello, Wing!"


def test_translate_plural_selects_on_params_n(page, server):
    import_i18n(page, server)
    got = page.evaluate("""
        async () => {
          const m = await import('/js/i18n/index.js');
          const dict = { en: { misc: { items: { one: '{n} item', other: '{n} items' } } } };
          return {
            singular: m.translate(dict, 'en', 'misc.items', { n: 1 }),
            plural: m.translate(dict, 'en', 'misc.items', { n: 5 }),
          };
        }
    """)
    assert got == {"singular": "1 item", "plural": "5 items"}


def test_translate_missing_key_returns_the_key_and_warns(page, server):
    import_i18n(page, server)
    got = page.evaluate("""
        async () => {
          const warnings = [];
          const orig = console.warn;
          console.warn = (...args) => warnings.push(args.join(' '));
          const m = await import('/js/i18n/index.js');
          const result = m.translate({ en: {} }, 'en', 'nope.here');
          console.warn = orig;
          return { result, warned: warnings.length > 0 };
        }
    """)
    assert got == {"result": "nope.here", "warned": True}


def test_t_against_the_real_empty_dictionary_falls_back_to_the_key(page, server):
    """Every real namespace ships empty in this phase — t() must degrade to
    the missing-key path for any real key, not silently swallow it."""
    import_i18n(page, server)
    got = page.evaluate("""
        async () => {
          const warnings = [];
          const orig = console.warn;
          console.warn = (...args) => warnings.push(args.join(' '));
          const m = await import('/js/i18n/index.js');
          const result = m.t('misc.doesNotExistYet');
          console.warn = orig;
          return { result, warned: warnings.length > 0 };
        }
    """)
    assert got == {"result": "misc.doesNotExistYet", "warned": True}


# ------------------------------ langUrl() ------------------------------

def test_lang_url_preserves_owner_and_hash(page, server):
    page.goto(
        f"{server}/?demo=1&owner={KNOWN_OWNER}#quality", wait_until="domcontentloaded")
    got = page.evaluate("""
        async () => {
          const m = await import('/js/i18n/index.js');
          const url = m.langUrl('en');
          return { search: url.search, hash: url.hash };
        }
    """)
    assert f"owner={KNOWN_OWNER}" in got["search"]
    assert "lang=en" in got["search"]
    assert got["hash"] == "#quality"


# ------------------------------ apply-dom.js ------------------------------

def test_apply_dom_sets_text_and_attrs_from_data_i18n(page, server):
    """No production markup carries data-i18n yet, so this exercises the
    applier against a synthetic fragment rather than the live page."""
    import_i18n(page, server)
    got = page.evaluate("""
        async () => {
          const dom = await import('/js/i18n/apply-dom.js');
          const div = document.createElement('div');
          div.innerHTML =
            '<span data-i18n="misc.hello"></span>' +
            '<input data-i18n-attr="placeholder:misc.hello,aria-label:misc.bye">';
          document.body.appendChild(div);
          dom.applyDom(div);
          const out = {
            text: div.querySelector('span').textContent,
            placeholder: div.querySelector('input').getAttribute('placeholder'),
            ariaLabel: div.querySelector('input').getAttribute('aria-label'),
          };
          div.remove();
          return out;
        }
    """)
    # keys are missing from the (empty) production dict, so t() falls back
    # to returning the key itself — proves the wiring, not real copy.
    assert got == {
        "text": "misc.hello",
        "placeholder": "misc.hello",
        "ariaLabel": "misc.bye",
    }


# --------------------------- localStorage persistence ---------------------------

def test_toggle_persists_choice_and_query_param_wins_over_storage(page, server):
    open_dashboard(page, server, "?demo=1")
    click_language(page, "en", "en")
    assert page.get_attribute("html", "lang") == "en"
    stored = page.evaluate("() => localStorage.getItem('dashboardLang')")
    assert stored == "en"

    # no ?lang param on a later load — stored preference applies
    open_dashboard(page, server, "?demo=1")
    assert page.get_attribute("html", "lang") == "en"

    # explicit ?lang=zh beats the stored 'en'
    open_dashboard(page, server, "?demo=1&lang=zh")
    assert page.get_attribute("html", "lang") == "zh-Hant"
