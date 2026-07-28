"""Unit tests for docs/js/people.js, executed in a real browser.

There is no JS test runner in this repo (no package.json), so pure frontend
logic is exercised by importing the ES module inside a Playwright page and
evaluating assertions there. The page is loaded with ?demo=1 so the module
resolves against a same-origin document without needing the private
metrics.json.

Run:  python -m pytest scripts/test_people_js.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="people.js unit tests need pytest-playwright")


def evaluate(page, server, body: str):
    """Import people.js in the page and return the value of `body`."""
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    return page.evaluate(
        "async () => { const m = await import('/js/people.js'); "
        f"return ({body}); }}"
    )


def test_build_person_index_maps_identities_to_canonical(page, server):
    got = evaluate(page, server, """
        (() => {
          const idx = m.buildPersonIndex({Wing: ['wing-csi', 'wing2036']});
          return [idx.get('wing-csi'), idx.get('wing2036'), idx.get('nobody') ?? null];
        })()
    """)
    assert got == ["Wing", "Wing", None]


def test_build_person_index_tolerates_missing_map(page, server):
    got = evaluate(page, server,
                   "[m.buildPersonIndex(null).size, m.buildPersonIndex({}).size]")
    assert got == [0, 0]


def test_person_of_falls_back_to_raw_author(page, server):
    """An unmapped identity is still a person — just not an aliased one."""
    got = evaluate(page, server, """
        (() => {
          const idx = m.buildPersonIndex({Wing: ['wing-csi', 'wing2036']});
          return [m.personOf('wing2036', idx), m.personOf('Shane', idx), m.personOf('', idx)];
        })()
    """)
    assert got == ["Wing", "Shane", ""]


def test_person_options_merges_aliases_and_sorts_by_count(page, server):
    got = evaluate(page, server, """
        (() => {
          const idx = m.buildPersonIndex({Wing: ['wing-csi', 'wing2036']});
          const tasks = [
            {author: 'wing-csi'}, {author: 'wing2036'}, {author: 'wing-csi'},
            {author: 'Tony'}, {author: 'Tony'}, {author: 'Tony'}, {author: 'Tony'},
            {author: ''},
          ];
          return m.personOptions(tasks, idx, () => true);
        })()
    """)
    assert got == [{"person": "Tony", "count": 4}, {"person": "Wing", "count": 3}]


def test_person_options_honours_scope_predicate(page, server):
    got = evaluate(page, server, """
        (() => {
          const idx = m.buildPersonIndex({});
          const tasks = [{author: 'a', repo: 'x'}, {author: 'b', repo: 'y'}];
          return m.personOptions(tasks, idx, (t) => t.repo === 'x');
        })()
    """)
    assert got == [{"person": "a", "count": 1}]
