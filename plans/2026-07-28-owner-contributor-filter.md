# Owner / Contributor Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a contributor `<select>` that re-scopes the dashboard to one person (merging their multiple GitHub identities), plus a declared project-owner grouping on the repo `<select>`.

**Architecture:** `config.toml` declares identity aliases (`[people]`) and a per-repo `owner`. The collector validates them and emits them into `metrics.json`; the frontend builds an `author → person` index once at load and filters through the single existing choke point `tasksBetween()`. Sections with no person dimension are neutralised and marked rather than left showing wrong numbers. See `specs/2026-07-28-owner-contributor-filter-design.md` (approved).

**Tech Stack:** Python 3.11+ stdlib + pytest (collector), vanilla ES modules (frontend, no build step), Playwright driven from pytest (frontend behaviour tests), GitHub Actions.

## Global Constraints

- **Spec:** `specs/2026-07-28-owner-contributor-filter-design.md`. It supersedes §#3 of `specs/2026-07-27-dashboard-enhancements-design.md`.
- **Test command:** `python -m pytest scripts/ -q` — must pass before every commit. Baseline before this plan starts: **109 passed, 0 skipped**.
- **Playwright was installed on 2026-07-28** (`playwright` + `pytest-playwright` + chromium). Before that the 3 tests in `scripts/test_frontend_snapshot.py` were dormant — the suite reported `106 passed, 1 skipped`. They now pass. If you see `fixture 'page' not found`, `pytest-playwright` is missing (the `playwright` package alone does not provide it).
- **Commit format:** `<type>: <description>` — types `feat, fix, refactor, docs, test, chore, perf, ci`. **No attribution or co-author footer.**
- **The collector is stdlib-only** (`scripts/collect_github.py` docstring: "Stdlib only (Python >= 3.11 for tomllib)"). Do not add a runtime dependency. Playwright is a *test-only* dependency.
- **Do not read `docs/data/demo-data.js`** — one 80,526-byte line, will overflow context.
- **Do not read `docs/data/metrics.json` wholesale** — ~1.2 MB of private client repo commit titles. Query it with a short `python -c` script if you need a fact from it.
- **`docs/data/metrics.json` must stay gitignored and untracked.** Never `git add` it.
- **`schema_version` stays at `2`.** Both new fields are optional; bumping would falsely signal that consumers must update.
- **Exact names** (used across tasks — do not rename): config keys `[people]` and `owner`; JSON keys `people` and `repo_meta[<repo>].owner`; element ids `personSel`, `repoSel`, `branchSel`; state fields `state.person`, `state.repo`; URL param `owner`; option values `all` and `owner:<Person>`; new module `docs/js/people.js`.
- **Escaping:** every person or owner string interpolated into HTML goes through the existing `esc()` from `docs/js/data.js`. The `?owner=` URL value is **never** rendered — it is only compared against the known person list.

## Context for someone with zero prior knowledge

This repo collects GitHub metrics for ~13 tracked repos nightly via
`.github/workflows/collect.yml`, writing `metrics.json` (~1.2 MB, 2,048 tasks).
A static dashboard in `docs/` (vanilla ES modules, no build step, Chart.js from
CDN) renders it. There is **no `package.json` and no JS test runner** — frontend
tests are Playwright driven from pytest against a fixture file.

A "task" is one merged PR or one non-merge commit. Each task carries an `author`
string. That string is a GitHub login for PRs, but for commits with no linked
GitHub account it falls back to the raw git display name
(`collect_github.py:515-517`). Live data has **18 distinct authors**, two of
which are the same human: `wing-csi` (375 tasks) and `wing2036` (78 tasks).
Merging those is the core correctness requirement of this feature.

The dashboard has three filters today (repo / branch / window). All task-derived
sections read through `tasksBetween()` in `docs/js/data.js`, which is the single
place repo and branch filtering happens. Two sections bypass it and are called
out explicitly in Tasks 5 and 6.

---

### Task 1: `[people]` alias config — parse and validate (TDD)

**Files:**
- Modify: `scripts/collect_github.py` (add `parse_people()`; call it from `load_config()` at `:889-900`)
- Test: `scripts/test_collect_github.py` (append to the config section that starts at `:496`)

**Interfaces:**
- Consumes: existing `load_config(path: Path) -> dict` and `CollectError`.
- Produces:
  - `parse_people(raw: dict) -> dict[str, list[str]]` — canonical name → identities. Returns `{}` when the `[people]` table is absent or empty. Raises `CollectError` on the invalid shapes below.
  - `load_config()` return dict gains key `"people"` with that value.

- [ ] **Step 1: Write the failing tests**

Append to `scripts/test_collect_github.py`:

```python
# ---------------------------------------------------------------- people

def test_parse_people_absent_returns_empty():
    from collect_github import parse_people
    assert parse_people({}) == {}


def test_parse_people_maps_canonical_to_identities():
    from collect_github import parse_people
    got = parse_people({"people": {"Wing": ["wing-csi", "wing2036"]}})
    assert got == {"Wing": ["wing-csi", "wing2036"]}


def test_parse_people_rejects_identity_under_two_people():
    from collect_github import parse_people
    with pytest.raises(CollectError, match="wing2036"):
        parse_people({"people": {"Wing": ["wing-csi", "wing2036"],
                                 "Shane": ["wing2036"]}})


def test_parse_people_rejects_empty_identity_list():
    from collect_github import parse_people
    with pytest.raises(CollectError, match="Wing"):
        parse_people({"people": {"Wing": []}})


def test_parse_people_rejects_non_string_identity():
    from collect_github import parse_people
    with pytest.raises(CollectError, match="Wing"):
        parse_people({"people": {"Wing": ["wing-csi", 7]}})


def test_parse_people_rejects_non_list_value():
    from collect_github import parse_people
    with pytest.raises(CollectError, match="Wing"):
        parse_people({"people": {"Wing": "wing-csi"}})


def test_load_config_carries_people(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        '[[repos]]\nname = "wing/abci"\n'
        '[people]\nWing = ["wing-csi", "wing2036"]\n'
    )
    cfg = load_config(cfg_file)
    assert cfg["people"] == {"Wing": ["wing-csi", "wing2036"]}


def test_load_config_without_people_is_empty(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[[repos]]\nname = "wing/abci"\n')
    assert load_config(cfg_file)["people"] == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest scripts/test_collect_github.py -k people -q`
Expected: FAIL — `ImportError: cannot import name 'parse_people'`

- [ ] **Step 3: Implement `parse_people()`**

Add to `scripts/collect_github.py`, immediately above `def load_config` (`:889`):

```python
def parse_people(raw: dict) -> dict[str, list[str]]:
    """Parse the optional [people] table: canonical name -> identities.

    One human can appear under several identities because commit authors fall
    back to the raw git display name when no GitHub account resolves
    (see collect_commits). Without merging, a per-person filter undercounts.

    Validation is strict and fails the whole run: a mis-typed alias silently
    splits or merges someone's work, which is worse than not collecting.
    """
    table = raw.get("people") or {}
    if not isinstance(table, dict):
        raise CollectError("[people] must be a table of name = [identities]")
    people: dict[str, list[str]] = {}
    seen: dict[str, str] = {}  # identity -> canonical name that claimed it
    for person, identities in table.items():
        if not isinstance(identities, list) or not identities:
            raise CollectError(
                f"[people] {person}: expected a non-empty list of identities")
        for ident in identities:
            if not isinstance(ident, str) or not ident:
                raise CollectError(
                    f"[people] {person}: identity {ident!r} is not a non-empty string")
            if ident in seen and seen[ident] != person:
                raise CollectError(
                    f"[people] identity {ident!r} is listed under both "
                    f"{seen[ident]!r} and {person!r}")
            seen[ident] = person
        people[person] = list(identities)
    return people
```

Then in `load_config()` add `"people": parse_people(raw),` to the returned dict.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest scripts/test_collect_github.py -k people -q`
Expected: PASS (8 tests)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest scripts/ -q`
Expected: 117 passed, 0 skipped

- [ ] **Step 6: Commit**

```bash
git add scripts/collect_github.py scripts/test_collect_github.py
git commit -m "feat: parse and validate [people] identity aliases"
```

---

### Task 2: Per-repo `owner` + emit both into metrics.json (TDD)

**Files:**
- Modify: `scripts/collect_github.py` (add `resolve_owner()` and `build_output()`; call `build_output()` from `main()` at `:951-960`)
- Test: `scripts/test_collect_github.py`

**Interfaces:**
- Consumes: `parse_people()` from Task 1; the `Task` dataclass; `cfg` dict from `load_config()`.
- Produces:
  - `resolve_owner(repo_cfg: dict, people: dict[str, list[str]]) -> str | None` — canonical person name for a repo's declared `owner`, or `None` when undeclared.
  - `build_output(cfg: dict, tasks: list, repo_meta: dict, errors: list[str], generated_at: str) -> dict` — assembles the `metrics.json` payload. Sets `repo_meta[<repo>]["owner"]` for repos that declare one, and a top-level `"people"` key.

Extracting `build_output()` from `main()` is deliberate: it gives the frontend
contract a unit-testable seam and keeps `main()` thin.

- [ ] **Step 1: Write the failing tests**

Append to `scripts/test_collect_github.py`:

```python
# ---------------------------------------------------------------- owner

def test_resolve_owner_undeclared_is_none():
    from collect_github import resolve_owner
    assert resolve_owner({"name": "wing/abci"}, {}) is None


def test_resolve_owner_passes_through_canonical_name():
    from collect_github import resolve_owner
    people = {"Wing": ["wing-csi", "wing2036"]}
    assert resolve_owner({"name": "wing/abci", "owner": "Wing"}, people) == "Wing"


def test_resolve_owner_maps_identity_to_canonical():
    from collect_github import resolve_owner
    people = {"Wing": ["wing-csi", "wing2036"]}
    assert resolve_owner({"name": "wing/abci", "owner": "wing2036"}, people) == "Wing"


def test_resolve_owner_unknown_name_passes_through():
    """An owner who never commits is legitimate (e.g. a manager)."""
    from collect_github import resolve_owner
    assert resolve_owner({"name": "wing/abci", "owner": "Alice"}, {}) == "Alice"


def test_build_output_emits_people_and_owner():
    from collect_github import build_output
    cfg = {
        "window_days": 90, "mode": "auto",
        "repos": [{"name": "wing/abci", "owner": "wing2036"},
                  {"name": "wing/other"}],
        "people": {"Wing": ["wing-csi", "wing2036"]},
    }
    repo_meta = {"wing/abci": {}, "wing/other": {}}
    out = build_output(cfg, [], repo_meta, [], "2026-07-28T05:00:00+00:00")
    assert out["schema_version"] == 2
    assert out["people"] == {"Wing": ["wing-csi", "wing2036"]}
    assert out["repo_meta"]["wing/abci"]["owner"] == "Wing"
    assert "owner" not in out["repo_meta"]["wing/other"]


def test_build_output_omits_people_key_when_unconfigured():
    from collect_github import build_output
    cfg = {"window_days": 90, "mode": "auto",
           "repos": [{"name": "wing/abci"}], "people": {}}
    out = build_output(cfg, [], {"wing/abci": {}}, [], "2026-07-28T05:00:00+00:00")
    assert out["people"] == {}
    assert out["repos"] == ["wing/abci"]


def test_build_output_warns_on_unknown_owner(capsys):
    from collect_github import build_output
    cfg = {"window_days": 90, "mode": "auto",
           "repos": [{"name": "wing/abci", "owner": "Wng"}],
           "people": {"Wing": ["wing-csi"]}}
    build_output(cfg, [], {"wing/abci": {}}, [], "2026-07-28T05:00:00+00:00")
    assert "Wng" in capsys.readouterr().err
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest scripts/test_collect_github.py -k "owner or build_output" -q`
Expected: FAIL — `ImportError: cannot import name 'resolve_owner'`

- [ ] **Step 3: Implement both functions**

Add to `scripts/collect_github.py` below `parse_people()`:

```python
def resolve_owner(repo_cfg: dict, people: dict[str, list[str]]) -> str | None:
    """Canonical person name for a repo's declared owner, or None.

    Accepts either a canonical name or any of that person's identities, so
    `owner = "wing2036"` and `owner = "Wing"` mean the same thing.
    """
    declared = repo_cfg.get("owner")
    if not declared:
        return None
    if declared in people:
        return declared
    for person, identities in people.items():
        if declared in identities:
            return person
    return declared


def build_output(cfg: dict, tasks: list, repo_meta: dict,
                 errors: list[str], generated_at: str) -> dict:
    """Assemble the metrics.json payload.

    schema_version stays at 2: `people` and `repo_meta[r].owner` are both
    optional, so old data and old frontends degrade gracefully in either
    direction.
    """
    known = set(cfg["people"]) | {i for ids in cfg["people"].values() for i in ids}
    task_authors = {t.author for t in tasks if t.author}
    for repo_cfg in cfg["repos"]:
        owner = resolve_owner(repo_cfg, cfg["people"])
        if owner is None:
            continue
        meta = repo_meta.get(repo_cfg["name"])
        if meta is None:
            continue
        meta["owner"] = owner
        if owner not in known and owner not in task_authors:
            # Not fatal: an owner who never commits is legitimate. But this is
            # also exactly how a typo looks, so say so.
            print(f"  ! warning: {repo_cfg['name']}: owner {owner!r} matches no "
                  "known person or task author", file=sys.stderr)
    return {
        "schema_version": 2,
        "generated_at": generated_at,
        "window_days": cfg["window_days"],
        "mode": cfg["mode"],
        "repos": [r["name"] for r in cfg["repos"]],
        "people": cfg["people"],
        "tasks": [asdict(t) for t in tasks],
        "repo_meta": repo_meta,
        "errors": errors,
    }
```

Then replace the inline `output = {...}` literal in `main()` (`:951-960`) with:

```python
    output = build_output(
        cfg, tasks, repo_meta, errors,
        datetime.now(timezone.utc).isoformat(timespec="seconds"))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest scripts/test_collect_github.py -k "owner or build_output" -q`
Expected: PASS (7 tests)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest scripts/ -q`
Expected: 124 passed, 0 skipped

- [ ] **Step 6: Commit**

```bash
git add scripts/collect_github.py scripts/test_collect_github.py
git commit -m "feat: resolve per-repo owner and emit people map to metrics.json"
```

---

### Task 3: Playwright in CI + `docs/js/people.js` pure module (TDD)

**Files:**
- Create: `docs/js/people.js`
- Create: `scripts/test_people_js.py`
- Modify: `scripts/conftest.py` (host the shared `server` fixture)
- Modify: `scripts/test_frontend_snapshot.py:41-81` (drop the moved helpers)
- Modify: `.github/workflows/collect.yml:22`

**Interfaces:**
- Consumes: nothing (pure module, no imports).
- Produces, all named exports of `docs/js/people.js`:
  - `buildPersonIndex(peopleMap: object) -> Map<string, string>` — `{"Wing":["wing-csi"]}` → `Map{"wing-csi" => "Wing"}`. Empty Map for `null`/`undefined`/`{}`.
  - `personOf(author: string, index: Map) -> string` — canonical name, falling back to `author` when unmapped; `''` for a falsy author.
  - `personOptions(tasks: array, index: Map, inScope: function) -> Array<{person: string, count: number}>` — counts tasks passing `inScope`, sorted by count descending then name ascending.

**Why this task also touches CI:** without Playwright installed, every frontend
test in Tasks 3–7 silently *skips*, and the existing `rendered-baseline.json`
guard has never actually run. Installing it here makes all later verification real.

- [ ] **Step 1: Add Playwright to CI**

`pytest-playwright` is what supplies the `page` fixture; the `playwright`
package alone is not enough. In `.github/workflows/collect.yml`, replace lines
22-23 with:

```yaml
          pip install pytest pyyaml pytest-playwright -q
          python3 -m playwright install --with-deps chromium
          python3 -m pytest scripts/ -q
```

- [ ] **Step 1b: Fix the guard that hid these tests**

`scripts/test_frontend_snapshot.py:21` guards on the wrong module name, so a
machine with `playwright` but not `pytest-playwright` gets a hard
`fixture 'page' not found` error instead of a clean skip. Change it to:

```python
pytest.importorskip("pytest_playwright", reason="frontend snapshot test needs pytest-playwright")
```

- [ ] **Step 2: Move the `server` fixture into `scripts/conftest.py`**

`test_people_js.py` and `test_frontend_snapshot.py` both need it. Append to
`scripts/conftest.py`:

```python
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

DOCS = Path(__file__).parent.parent / "docs"


def _pick_free_port() -> int:
    """Ask the OS for an unused TCP port instead of hardcoding one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> None:
    """Poll until something accepts TCP connections on host:port."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.2)
    raise RuntimeError(f"server on {host}:{port} did not become reachable within {timeout}s")


@pytest.fixture(scope="session")
def server():
    port = _pick_free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "-d", str(DOCS)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_port("127.0.0.1", port)
    except RuntimeError:
        proc.terminate()
        proc.wait(timeout=5)
        raise
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    proc.wait(timeout=5)
```

Then delete `_pick_free_port`, `_wait_for_port` and the `server` fixture from
`scripts/test_frontend_snapshot.py` (`:41-81`), keeping its `DOCS`, `FIXTURES`
and `BASELINE` constants and its now-unused `socket`/`subprocess`/`sys`/`time`
imports removed.

- [ ] **Step 3: Write the failing tests**

Create `scripts/test_people_js.py`:

```python
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

pytest.importorskip("pytest_playwright", reason="people.js unit tests need pytest-playwright")


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
    got = evaluate(page, server, "[m.buildPersonIndex(null).size, m.buildPersonIndex({}).size]")
    assert got == [0, 0]


def test_person_of_falls_back_to_raw_author(page, server):
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
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `python -m pytest scripts/test_people_js.py -q`
Expected: FAIL — the dynamic import 404s because `docs/js/people.js` does not exist.

- [ ] **Step 5: Implement `docs/js/people.js`**

```js
/* Identity resolution for the contributor filter.
 *
 * One human can appear under several identities: PR authors are GitHub logins,
 * but commit authors fall back to the raw git display name when no GitHub
 * account resolves. Aliases are declared in config.toml [people] and arrive
 * here via metrics.json, rather than being guessed — metrics.json carries no
 * author email to key on.
 */

/** {"Wing": ["wing-csi", "wing2036"]} -> Map{"wing-csi" => "Wing", ...} */
export function buildPersonIndex(peopleMap) {
  const index = new Map();
  for (const [person, identities] of Object.entries(peopleMap || {})) {
    for (const identity of identities || []) index.set(identity, person);
  }
  return index;
}

/** Canonical person for an author, falling back to the author itself. */
export function personOf(author, index) {
  if (!author) return '';
  return index.get(author) || author;
}

/** [{person, count}] for tasks passing `inScope`, busiest first. */
export function personOptions(tasks, index, inScope) {
  const counts = new Map();
  for (const t of tasks || []) {
    if (!t.author || !inScope(t)) continue;
    const person = personOf(t.author, index);
    counts.set(person, (counts.get(person) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([person, count]) => ({ person, count }))
    .sort((a, b) => b.count - a.count || (a.person < b.person ? -1 : 1));
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest scripts/test_people_js.py -q`
Expected: PASS (5 tests)

- [ ] **Step 7: Confirm the snapshot guard still runs**

Run: `python -m pytest scripts/test_frontend_snapshot.py -q`
Expected: PASS (3 tests), **not** skipped. Moving the `server` fixture in Step 2
is the risk here — if collection errors with `fixture 'server' not found`, the
fixture did not land in `scripts/conftest.py` correctly.

- [ ] **Step 8: Run the full suite**

Run: `python -m pytest scripts/ -q`
Expected: 129 passed, 0 skipped

- [ ] **Step 9: Commit**

```bash
git add docs/js/people.js scripts/test_people_js.py scripts/conftest.py scripts/test_frontend_snapshot.py .github/workflows/collect.yml
git commit -m "feat: people.js identity index, with playwright wired into CI"
```

---

### Task 4: `repoInScope()` / `singleRepo()` refactor (behaviour-preserving)

**Files:**
- Modify: `docs/js/data.js` (add both helpers; use in `tasksBetween` at `:32`)
- Modify: `docs/js/aggregate.js:121`, `:135`
- Modify: `docs/js/render-kpi.js:220`
- Modify: `docs/js/render-project.js:35`, `:76`, `:92`
- Modify: `docs/js/render-table.js:20`, `:45`, `:77`

**Interfaces:**
- Consumes: `state` from `docs/js/data.js`.
- Produces, exported from `docs/js/data.js`:
  - `OWNER_PREFIX` — the string `'owner:'`.
  - `repoInScope(repo: string) -> boolean` — true when `repo` is inside the current `state.repo` selection. Handles `'all'`, an exact repo name, and (from Task 7) `'owner:<Person>'`.
  - `singleRepo() -> string | null` — the selected repo name, or `null` when the selection covers more than one repo.

**This task changes no behaviour.** `state.repo` still only ever holds `'all'`
or a repo name; the `owner:` form arrives in Task 7. The point is to centralise
ten copies of the same conditional *before* widening what `state.repo` can hold,
so Task 7 cannot miss one. The snapshot baseline is the proof of no change.

- [ ] **Step 1: Confirm the baseline is green before touching anything**

Run: `python -m pytest scripts/test_frontend_snapshot.py -q`
Expected: PASS (3 tests)

- [ ] **Step 2: Add the helpers to `docs/js/data.js`**

Insert after the `esc` definition (`:6`):

```js
/* ---------------- repo scope ----------------
 * state.repo holds 'all', an exact repo name, or 'owner:<Person>'. Every
 * consumer asks this predicate instead of comparing state.repo directly, so
 * the owner form cannot be silently missed at one of the call sites.
 */
export const OWNER_PREFIX = 'owner:';
export function repoInScope(repo) {
  if (state.repo === 'all') return true;
  if (state.repo.startsWith(OWNER_PREFIX)) {
    const person = state.repo.slice(OWNER_PREFIX.length);
    return ((state.data.repo_meta || {})[repo] || {}).owner === person;
  }
  return repo === state.repo;
}
/** The selected repo name, or null when the selection spans several repos. */
export function singleRepo() {
  if (state.repo === 'all' || state.repo.startsWith(OWNER_PREFIX)) return null;
  return state.repo;
}
```

- [ ] **Step 3: Replace all ten call sites**

In `docs/js/data.js:32`, inside `tasksBetween`:

```js
    if (!repoInScope(t.repo)) return false;
```

In `docs/js/aggregate.js`, add `repoInScope` to the import from `./data.js`, then
at `:121` and `:135` replace `if (state.repo !== 'all' && repo !== state.repo) continue;` with:

```js
    if (!repoInScope(repo)) continue;
```

Apply the identical replacement at `docs/js/render-kpi.js:220`,
`docs/js/render-project.js:35`, `:76`, `:92`, and `docs/js/render-table.js:20`
and `:77`, adding `repoInScope` to each file's import from `./data.js`.

In `docs/js/render-table.js:45` the condition is inline inside a `.filter()`:

```js
  for (const t of (state.data.tasks || []).filter((t) => repoInScope(t.repo) && (state.branch === 'all' || t.branch === state.branch))) {
```

- [ ] **Step 4: Verify nothing changed**

Run: `python -m pytest scripts/test_frontend_snapshot.py -q`
Expected: PASS — byte-identical rendered output. A failure here means the
refactor changed behaviour; fix it rather than regenerating the baseline.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest scripts/ -q`
Expected: 129 passed, 0 skipped

- [ ] **Step 6: Commit**

```bash
git add docs/js/
git commit -m "refactor: centralise repo scope checks behind repoInScope()"
```

---

### Task 5: Contributor filter — state, dropdown, URL (TDD)

**Files:**
- Modify: `docs/index.html:29` (add `<select id="personSel">` after `branchSel`)
- Modify: `docs/js/data.js` (add `person` + `personIndex` to `state`; filter in `tasksBetween`)
- Modify: `docs/js/main.js` (build the dropdown, wire the event, read/write the URL)
- Modify: `docs/js/render-table.js:45` (月度活躍 bypasses `tasksBetween`)
- Create: `scripts/fixtures/metrics-fixture-people.json`
- Create: `scripts/test_frontend_people.py`

**Interfaces:**
- Consumes: `buildPersonIndex`, `personOptions`, `personOf` from Task 3; `repoInScope`, `singleRepo` from Task 4.
- Produces: `state.person` (`'all'` or a canonical person name); `state.personIndex` (the Map); `personInScope(task) -> boolean` exported from `docs/js/data.js`, used by 月度活躍 and by Task 6.

**Do not touch `scripts/fixtures/metrics-fixture.json` or
`rendered-baseline.json`.** Their whole value is proving the default render did
not shift.

- [ ] **Step 1: Create the people fixture**

Create `scripts/fixtures/metrics-fixture-people.json` — two repos, two humans,
one of them under two identities:

```json
{
 "schema_version": 2,
 "generated_at": "2026-07-28T05:00:00+00:00",
 "window_days": 180,
 "mode": "auto",
 "repos": ["acme/alpha", "acme/beta"],
 "people": {"Wing": ["wing-csi", "wing2036"]},
 "tasks": [
  {"date": "2026-07-20", "repo": "acme/alpha", "author": "wing-csi", "id": "1", "kind": "pr", "branch": "main", "title": "feat: alpha one", "level": "L3", "method": "label", "check": null, "additions": 40, "deletions": 2, "url": "https://example.test/1", "rework": 0, "violations": [], "lead_hours": 5, "ci": "pass"},
  {"date": "2026-07-19", "repo": "acme/alpha", "author": "wing2036", "id": "a1b2c3d", "kind": "commit", "branch": "main", "title": "fix: alpha two", "level": "L2", "method": "rule", "check": null, "additions": 12, "deletions": 3, "url": "https://example.test/2", "rework": 0, "violations": []},
  {"date": "2026-07-18", "repo": "acme/alpha", "author": "Tony", "id": "2", "kind": "pr", "branch": "main", "title": "feat: alpha three", "level": "L4", "method": "label", "check": null, "additions": 90, "deletions": 10, "url": "https://example.test/3", "rework": 1, "violations": [], "lead_hours": 30, "ci": "pass"},
  {"date": "2026-07-17", "repo": "acme/beta", "author": "Tony", "id": "3", "kind": "pr", "branch": "main", "title": "revert: beta one", "level": "L1", "method": "rule", "check": null, "additions": 5, "deletions": 60, "url": "https://example.test/4", "rework": 0, "violations": [], "lead_hours": 2, "ci": "fail"}
 ],
 "repo_meta": {
  "acme/alpha": {"owner": "Wing", "disk_kb": 1024, "languages": {"items": [{"name": "Python", "bytes": 5000}]}, "deployments": ["2026-07-20T00:00:00Z"], "releases": [], "tags": [], "closed_unmerged": [], "issues": null},
  "acme/beta": {"disk_kb": 512, "languages": {"items": [{"name": "JavaScript", "bytes": 2000}]}, "deployments": [], "releases": [], "tags": [], "closed_unmerged": [], "issues": null}
 },
 "errors": []
}
```

- [ ] **Step 2: Write the failing tests**

Create `scripts/test_frontend_people.py`:

```python
"""Behaviour tests for the contributor filter.

Uses its own fixture so metrics-fixture.json and rendered-baseline.json stay
untouched — their value is proving the *default* render did not shift.

Run:  python -m pytest scripts/test_frontend_people.py -v
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytest.importorskip("pytest_playwright", reason="contributor filter tests need pytest-playwright")

DOCS = Path(__file__).parent.parent / "docs"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def people_data():
    """Swap the people fixture in as docs/data/metrics.json for one test."""
    target = DOCS / "data" / "metrics.json"
    backup = DOCS / "data" / "metrics.json.people-backup"
    had_original = target.exists()
    try:
        if had_original:
            shutil.move(target, backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIXTURES / "metrics-fixture-people.json", target)
        yield
    finally:
        if had_original and backup.exists():
            shutil.move(backup, target)
        elif not had_original:
            target.unlink(missing_ok=True)


def authors_in_table(page) -> list[str]:
    return page.eval_on_selector_all(
        "#taskRows tr td:nth-child(3)", "els => els.map(e => e.textContent.trim())")


def test_person_options_merge_aliases(page, server, people_data):
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#taskRows tr")
    labels = page.eval_on_selector_all(
        "#personSel option", "els => els.map(e => e.textContent.trim())")
    assert labels[0].startswith("全部")
    # Wing = wing-csi + wing2036 = 2 tasks; Tony = 2 tasks
    assert "Wing (2)" in labels and "Tony (2)" in labels
    assert "wing2036" not in " ".join(labels)


def test_selecting_person_includes_aliased_tasks(page, server, people_data):
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#taskRows tr")
    page.select_option("#personSel", "Wing")
    assert sorted(authors_in_table(page)) == ["wing-csi", "wing2036"]


def test_owner_url_param_applies_on_load(page, server, people_data):
    page.goto(f"{server}/?owner=Wing", wait_until="networkidle")
    page.wait_for_selector("#taskRows tr")
    assert page.input_value("#personSel") == "Wing"
    assert sorted(authors_in_table(page)) == ["wing-csi", "wing2036"]


def test_selection_is_written_to_the_url(page, server, people_data):
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#taskRows tr")
    page.select_option("#personSel", "Tony")
    assert "owner=Tony" in page.url
    page.select_option("#personSel", "all")
    assert "owner=" not in page.url


@pytest.mark.parametrize("bad", ["nobody", "<img src=x onerror=alert(1)>"])
def test_unknown_owner_param_falls_back_without_injecting(page, server, people_data, bad):
    page.goto(f"{server}/?owner={bad}", wait_until="networkidle")
    page.wait_for_selector("#taskRows tr")
    assert page.input_value("#personSel") == "all"
    assert page.is_hidden("#loadError")
    assert len(authors_in_table(page)) == 4
    assert page.eval_on_selector("#personSel", "el => el.querySelector('img')") is None


def test_switching_repo_resets_a_person_with_no_tasks(page, server, people_data):
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#taskRows tr")
    page.select_option("#personSel", "Wing")
    page.select_option("#repoSel", "acme/beta")   # Wing has no tasks here
    assert page.input_value("#personSel") == "all"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest scripts/test_frontend_people.py -q`
Expected: FAIL — no `#personSel` element exists.

- [ ] **Step 4: Add the select to `docs/index.html`**

Insert after the `branchSel` line (`:29`):

```html
      <select id="personSel" aria-label="貢獻者"></select>
```

- [ ] **Step 5: Add person state and filtering to `docs/js/data.js`**

Import `personOf` at the top:

```js
import { personOf } from './people.js';
```

Add `person: 'all'` and `personIndex: new Map()` to the `state` object (`:3`).
Add below `singleRepo()`:

```js
/** True when a task belongs to the selected person (always true at 'all'). */
export function personInScope(task) {
  if (state.person === 'all') return true;
  return personOf(task.author, state.personIndex) === state.person;
}
```

Then add to `tasksBetween` (`:32`), directly after the `repoInScope` check:

```js
    if (!personInScope(t)) return false;
```

- [ ] **Step 6: Build the dropdown and URL wiring in `docs/js/main.js`**

Update the imports:

```js
import { state, $, esc, loadData, windowTasks, precedingTasks, LoadError, repoInScope, singleRepo } from './data.js';
import { buildPersonIndex, personOptions } from './people.js';
```

After `state.demo = demo;` (`:42`) add:

```js
  state.personIndex = buildPersonIndex(data.people);
```

Replace the `rebuildBranches` definition and the event wiring (`:54-78`) with:

```js
  const rebuildBranches = () => {
    const sel = $('branchSel');
    const only = singleRepo();
    if (!only) {
      // branch 名喺唔同 repo 之間冇比較意義 — 唔係單一 repo 就鎖死
      state.branch = 'all';
      sel.innerHTML = `<option value="all">全部 branches</option>`;
      sel.disabled = true;
      sel.title = '揀咗單一 repo 先可以 filter branch';
      return;
    }
    sel.disabled = false;
    sel.title = '';
    const set = new Set();
    for (const t of state.data.tasks || []) {
      if (t.repo === only && t.branch) set.add(t.branch);
    }
    const branches = [...set].sort();
    if (state.branch !== 'all' && !set.has(state.branch)) state.branch = 'all';
    sel.innerHTML = `<option value="all">全部 branches</option>` +
      branches.map((b) => `<option value="${esc(b)}"${b === state.branch ? ' selected' : ''}>${esc(b)}</option>`).join('');
  };

  const syncOwnerParam = () => {
    const url = new URL(location.href);
    if (state.person === 'all') url.searchParams.delete('owner');
    else url.searchParams.set('owner', state.person);
    history.replaceState(null, '', url);
  };

  // 人係跨 repo 可比較嘅(同 branch 唔同),所以全部 repos 時一樣開住
  const rebuildPeople = () => {
    const inScope = (t) => repoInScope(t.repo) && (state.branch === 'all' || t.branch === state.branch);
    const opts = personOptions(state.data.tasks || [], state.personIndex, inScope);
    if (state.person !== 'all' && !opts.some((o) => o.person === state.person)) {
      state.person = 'all';
    }
    $('personSel').innerHTML = `<option value="all">全部成員</option>` +
      opts.map((o) => `<option value="${esc(o.person)}"${o.person === state.person ? ' selected' : ''}>${esc(o.person)} (${o.count})</option>`).join('');
    syncOwnerParam();
  };

  // ?owner= 係唔可信輸入:淨係攞去同已知名單比對,唔會 render
  const requested = new URLSearchParams(location.search).get('owner');
  if (requested) {
    const known = personOptions(state.data.tasks || [], state.personIndex, () => true);
    if (known.some((o) => o.person === requested)) state.person = requested;
  }

  rebuildBranches();
  rebuildPeople();
  $('repoSel').addEventListener('change', (e) => { state.repo = e.target.value; rebuildBranches(); rebuildPeople(); render(); });
  $('branchSel').addEventListener('change', (e) => { state.branch = e.target.value; rebuildPeople(); render(); });
  $('personSel').addEventListener('change', (e) => { state.person = e.target.value; syncOwnerParam(); render(); });
  $('windowSel').addEventListener('change', (e) => { state.windowDays = +e.target.value; render(); });
```

- [ ] **Step 7: Apply the person filter to 月度活躍**

`docs/js/render-table.js:45` bypasses `tasksBetween`. Import `personInScope`
from `./data.js` and change the loop to:

```js
  for (const t of (state.data.tasks || []).filter((t) => repoInScope(t.repo) && personInScope(t) && (state.branch === 'all' || t.branch === state.branch))) {
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `python -m pytest scripts/test_frontend_people.py -q`
Expected: PASS (7 tests — the injection test is parametrized twice)

- [ ] **Step 9: Verify the default render still did not shift**

Run: `python -m pytest scripts/test_frontend_snapshot.py -q`
Expected: PASS. `#personSel` lives in the masthead, not in any of the eight
snapshot section ids, and the filter defaults to `all`.

- [ ] **Step 10: Run the full suite**

Run: `python -m pytest scripts/ -q`
Expected: 136 passed, 0 skipped

- [ ] **Step 11: Commit**

```bash
git add docs/index.html docs/js/ scripts/fixtures/metrics-fixture-people.json scripts/test_frontend_people.py
git commit -m "feat: contributor filter with alias merging and shareable ?owner= link"
```

---

### Task 6: Neutralise sections with no person dimension (TDD)

**Files:**
- Modify: `docs/js/data.js` (`tasksBetween`/`windowTasks` gain an `allPeople` option)
- Modify: `docs/js/render-kpi.js` (`renderDora` `:172-190`; `repoRag` `:192-197`; add `setScopeNotes`)
- Modify: `docs/js/render-table.js:53-63` (contributors stay team-wide)
- Modify: `docs/js/main.js` (eyebrow; call `setScopeNotes` from `render()`)
- Modify: `docs/index.html` (marker spans)
- Modify: `docs/css/dashboard.css` (`.scope-note`, `.contrib.is-selected`)
- Test: `scripts/test_frontend_people.py`

**Interfaces:**
- Consumes: `state.person`, `personInScope` from Task 5; `personOf` from Task 3.
- Produces:
  - `setScopeNotes(active: boolean)` exported from `docs/js/render-kpi.js` — toggles every `.scope-note`; called once per `render()`.
  - `renderEyebrow()` exported from `docs/js/main.js`.
  - `tasksBetween(fromMs, toMs, {allPeople})` and `windowTasks(opts)` gain the option.

- [ ] **Step 1: Write the failing tests**

Append to `scripts/test_frontend_people.py`:

```python
def test_cfr_is_blanked_for_a_person(page, server, people_data):
    """One person's reverts over the whole repo's deploys is not a rate."""
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#taskRows tr")
    assert page.text_content("#dCfr").strip() != "–"
    page.select_option("#personSel", "Wing")
    assert page.text_content("#dCfr").strip() == "–"


def test_contributors_stay_team_wide(page, server, people_data):
    """It is the comparison view and the place you pick a person from."""
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#taskRows tr")
    page.select_option("#personSel", "Wing")
    names = page.eval_on_selector_all(
        "#ovContribs .contrib .nm span[title]", "els => els.map(e => e.title)")
    assert "Tony" in names and "Wing" in names
    assert page.eval_on_selector_all(
        "#ovContribs .contrib.is-selected", "els => els.length") == 1


def test_scope_notes_appear_only_when_filtered(page, server, people_data):
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#taskRows tr")
    visible = "els => els.filter(e => !e.hidden).length"
    assert page.eval_on_selector_all(".scope-note", visible) == 0
    page.select_option("#personSel", "Wing")
    assert page.eval_on_selector_all(".scope-note", visible) > 0


def test_eyebrow_names_the_filtered_person(page, server, people_data):
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#taskRows tr")
    page.select_option("#personSel", "Wing")
    assert "Wing" in page.text_content("#eyebrow")


def test_rag_ignores_the_person_filter(page, server, people_data):
    """repoRag() calls windowTasks(); without pinning, its CI rate would
    silently become one person's PRs while coverage stays repo-wide."""
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#taskRows tr")
    before = page.inner_html("#ragRow")
    page.select_option("#personSel", "Wing")
    assert page.inner_html("#ragRow") == before
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest scripts/test_frontend_people.py -k "cfr or contributors or scope_notes or eyebrow or rag" -q`
Expected: FAIL — `#dCfr` still shows a number and no `.scope-note` elements exist.

- [ ] **Step 3: Add the `allPeople` option in `docs/js/data.js`**

```js
export function tasksBetween(fromMs, toMs, { allPeople = false } = {}) {
  return state.data.tasks.filter((t) => {
    if (!repoInScope(t.repo)) return false;
    if (!allPeople && !personInScope(t)) return false;
    if (state.branch !== 'all' && t.branch !== state.branch) return false;
    const ms = toDate(t.date).getTime();
    return ms >= fromMs && ms < toMs;
  });
}
export function windowTasks(opts) {
  const end = refDate().getTime() + 864e5;
  return tasksBetween(end - state.windowDays * 864e5, end, opts);
}
```

- [ ] **Step 4: Add the markers to `docs/index.html`**

Add `<span class="scope-note" hidden>全 repo 範圍</span>` to the `.card-head` of
品質 × 自動化 (`:117-119`), 項目進度 (`:153-155`) and Defect 追蹤 (`:186-188`);
beside the 部署頻率 label (`:69`); and inside the Codebase 語言構成 heading (`:177`).

- [ ] **Step 5: Style it in `docs/css/dashboard.css`**

Append:

```css
.scope-note{font-size:11px;color:var(--muted);border:1px solid var(--line);
  border-radius:3px;padding:1px 5px;margin-left:6px;white-space:nowrap}
.contrib.is-selected{outline:2px solid #24407E;outline-offset:2px;border-radius:4px}
```

- [ ] **Step 6: Blank the CFR and pin the RAG in `docs/js/render-kpi.js`**

In `renderDora`, replace the `cfr` lines (`:187-188`) with:

```js
  // 一個人嘅 revert ÷ 全 repo 部署次數 唔係一個比率 — 淨係喺全員視角先計
  const cfr = (state.person === 'all' && deployEvents)
    ? (cur.failTasks / deployEvents) * 100 : null;
  $('dCfr').innerHTML = cfr == null ? '–' : Math.min(cfr, 100).toFixed(0) + '<span class="unit">%</span>';
```

In `repoRag`, pin the person alongside the existing repo pin (`:193-197`):

```js
function repoRag(repo) {
  const saved = state.repo;
  const savedPerson = state.person;
  state.repo = repo;
  state.person = 'all';   // RAG 係 repo 級指標:唔可以變成某個人嘅 CI pass rate
  const cur = statsFromTasks(windowTasks());
  const meta = metaInWindow();
  state.repo = saved;
  state.person = savedPerson;
```

Add at the end of the file:

```js
/** Mark the sections that keep repo-wide numbers while a person is selected. */
export function setScopeNotes(active) {
  for (const el of document.querySelectorAll('.scope-note')) el.hidden = !active;
}
```

- [ ] **Step 7: Keep contributors team-wide in `docs/js/render-table.js`**

Import `personOf` from `./people.js`. Replace the contributors source loop (`:54-55`):

```js
  // 貢獻者係比較視角,亦係揀人嘅入口 — 保持全員,只標示揀咗邊個
  const by = {};
  for (const t of windowTasks({ allPeople: true })) {
    if (!t.author) continue;
    const p = personOf(t.author, state.personIndex);
    by[p] = (by[p] || 0) + 1;
  }
```

and add the highlight class to the generated markup (`:59`):

```js
  $('ovContribs').innerHTML = ce.map(([n, c], i) => `<div class="contrib${n === state.person ? ' is-selected' : ''}">
```

- [ ] **Step 8: Update the eyebrow and call `setScopeNotes` in `docs/js/main.js`**

Import `setScopeNotes` from `./render-kpi.js`. Add this function and call it from
`render()` as well as at init, replacing the inline eyebrow assignment (`:46`):

```js
export function renderEyebrow() {
  const repos = state.data.repos || [];
  const base = (repos.length === 1 ? repos[0].toUpperCase() : `${repos.length} REPOS`) + ' · GITHUB TELEMETRY';
  $('eyebrow').textContent = state.person === 'all' ? base : `${base} · 負責人 ${state.person}`;
}
```

Inside `render()`, add as the first two lines:

```js
  setScopeNotes(state.person !== 'all');
  renderEyebrow();
```

- [ ] **Step 9: Run the tests to verify they pass**

Run: `python -m pytest scripts/test_frontend_people.py -q`
Expected: PASS (12 tests)

- [ ] **Step 10: Verify the default render still did not shift**

Run: `python -m pytest scripts/test_frontend_snapshot.py -q`
Expected: PASS. All markers are `hidden` at `state.person === 'all'`, and none
of them live inside the eight snapshot section ids.

- [ ] **Step 11: Run the full suite**

Run: `python -m pytest scripts/ -q`
Expected: 141 passed, 0 skipped

- [ ] **Step 12: Commit**

```bash
git add docs/
git commit -m "feat: keep repo-level metrics honest under a person filter"
```

---

### Task 7: Owner grouping on the repo select (TDD)

**Files:**
- Modify: `docs/js/main.js` (build `repoSel` options with optgroups)
- Modify: `docs/js/render-project.js:38-58` (owner chip)
- Modify: `scripts/fixtures/rendered-baseline.json` (deliberate regeneration — see Step 6)
- Test: `scripts/test_frontend_people.py`

**Interfaces:**
- Consumes: `repoInScope`/`singleRepo`/`OWNER_PREFIX` from Task 4 (which already understand `owner:<Person>`); `repo_meta[<repo>].owner` from Task 2.
- Produces: no new exports. `state.repo` may now hold `owner:<Person>`.

- [ ] **Step 1: Write the failing tests**

Append to `scripts/test_frontend_people.py`:

```python
def test_owner_optgroup_lists_declared_owners(page, server, people_data):
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#taskRows tr")
    values = page.eval_on_selector_all(
        "#repoSel option", "els => els.map(e => e.value)")
    assert "owner:Wing" in values
    assert page.eval_on_selector_all(
        "#repoSel optgroup", "els => els.length") == 2


def test_owner_selection_scopes_to_that_owners_repos(page, server, people_data):
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#taskRows tr")
    page.select_option("#repoSel", "owner:Wing")
    repos = page.eval_on_selector_all(
        "#taskRows tr td:nth-child(2)", "els => els.map(e => e.textContent.trim())")
    assert set(repos) == {"alpha"}          # acme/beta has no owner


def test_owner_selection_disables_branch_select(page, server, people_data):
    """Branch names are not comparable across repos, same as 全部 repos."""
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#taskRows tr")
    page.select_option("#repoSel", "owner:Wing")
    assert page.is_disabled("#branchSel")


def test_owner_chip_shows_on_project_progress(page, server, people_data):
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#projChips .chip-rag")
    text = page.text_content("#projChips")
    assert "Wing" in text and "未指定" in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest scripts/test_frontend_people.py -k owner_ -q`
Expected: FAIL — `#repoSel` has no `optgroup` elements.

- [ ] **Step 3: Build the grouped repo select in `docs/js/main.js`**

Replace the `$('repoSel').innerHTML = ...` assignment (`:47-48`) with:

```js
  // 負責人 = repo 層面嘅 scoping,所以擺喺 repo select 入面,唔開第四個掣
  const rm = data.repo_meta || {};
  const ownerCounts = new Map();
  for (const r of repos) {
    const owner = (rm[r] || {}).owner;
    if (owner) ownerCounts.set(owner, (ownerCounts.get(owner) || 0) + 1);
  }
  const ownerGroup = ownerCounts.size
    ? `<optgroup label="按負責人">` + [...ownerCounts.entries()]
        .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))
        .map(([o, n]) => `<option value="owner:${esc(o)}">${esc(o)} 的項目 (${n})</option>`).join('')
      + `</optgroup>`
    : '';
  const repoGroup = ownerCounts.size
    ? `<optgroup label="個別 repo">` + repos.map((r) => `<option value="${esc(r)}">${esc(r)}</option>`).join('') + `</optgroup>`
    : repos.map((r) => `<option value="${esc(r)}">${esc(r)}</option>`).join('');
  $('repoSel').innerHTML = `<option value="all">全部 repos</option>` + ownerGroup + repoGroup;
```

No change is needed to the `repoSel` change handler — `repoInScope()` and
`singleRepo()` from Task 4 already understand the `owner:` form.

- [ ] **Step 4: Add the owner chip in `docs/js/render-project.js`**

Inside the repo loop (`:38-58`), build the label once after `const plan = ...`:

```js
    const owner = (rm[repo] || {}).owner;
    const ownerBit = ` <span style="color:var(--muted)">· 負責人 ${esc(owner || '未指定')}</span>`;
```

Append `${ownerBit}` to each of the three `el.innerHTML = ...` assignments in
that loop (the plan-file branch, the no-issues branch, and the risk branch).

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest scripts/test_frontend_people.py -k owner_ -q`
Expected: PASS (4 tests)

- [ ] **Step 6: Regenerate the snapshot baseline deliberately**

Run: `python -m pytest scripts/test_frontend_snapshot.py -q`
Expected: **FAIL on `#projChips`** — the owner chip adds `· 負責人 未指定` to
every repo chip, and `#projChips` *is* one of the eight snapshot ids. Inspect the
reported diff and confirm it contains only that added span and nothing else, then:

```bash
python -m pytest scripts/test_frontend_snapshot.py --snapshot-update -q
python -m pytest scripts/test_frontend_snapshot.py -q
```

Expected after regeneration: PASS. Then run `git diff scripts/fixtures/rendered-baseline.json`
and confirm every changed line is a `#projChips` owner span.

- [ ] **Step 7: Run the full suite**

Run: `python -m pytest scripts/ -q`
Expected: 145 passed, 0 skipped

- [ ] **Step 8: Commit**

```bash
git add docs/js/main.js docs/js/render-project.js scripts/test_frontend_people.py scripts/fixtures/rendered-baseline.json
git commit -m "feat: group repos by declared project owner"
```

---

### Task 8: Document the feature and configure the real owners

**Files:**
- Modify: `config.toml` (add `[people]`, add `owner` to the BoostBank repo)
- Modify: `README.md` (document both config keys and the filter)

**Interfaces:**
- Consumes: everything above.
- Produces: no code. This is what makes the feature live for the real dataset.

- [ ] **Step 1: Add the confirmed alias to `config.toml`**

Append a `[people]` block near `[classify]`. `wing-csi` and `wing2036` are the
same human — the repo-owner account and this machine's collaborator credential:

```toml
# ---- 身份合併(一個人有幾個 GitHub / git 身份)----
# PR 用 GitHub login,冇 link GitHub 帳號嘅 commit 會 fallback 去 git display
# name。唔合併嘅話,per-person filter 會少計。
[people]
Wing = ["wing-csi", "wing2036"]
```

- [ ] **Step 2: Declare the project owner asked for**

Add `owner = "Wing"` to the BoostBank repo entry (`config.toml:108-113`):

```toml
[[repos]]
name = "benegg/BoostBank-ReactNative-SMEApp"
token_env = "BEN_GH_METRICS_TOKEN"
owner = "Wing"
sop_paths = []
# main 排首名:共享 commits 歸 main,兩條工作 branch 嘅獨有 commits 各自入帳
branches = ["main", "Refactor", "product-selection-update"]
```

- [ ] **Step 3: Verify the config parses**

```bash
python -c "import sys; sys.path.insert(0,'scripts'); from collect_github import load_config; from pathlib import Path; c=load_config(Path('config.toml')); print(c['people']); print([(r['name'], r.get('owner')) for r in c['repos'] if r.get('owner')])"
```

Expected: `{'Wing': ['wing-csi', 'wing2036']}` and one
`('benegg/BoostBank-ReactNative-SMEApp', 'Wing')` row.

- [ ] **Step 4: Document both keys in `README.md`**

Add a subsection under the existing config documentation covering: the `[people]`
table (canonical name → identities, why merging is needed, that validation is
strict and fails the run), the per-repo `owner` key (accepts a canonical name or
any identity; an unknown name warns but does not fail, because an owner who never
commits is legitimate), the contributor `<select>`, the `?owner=` link, and the
fact that 部署頻率 / 品質 RAG / 項目進度 / Defect 追蹤 / 語言構成 stay repo-wide
and are marked 「全 repo 範圍」 while 變更失敗率 blanks entirely.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest scripts/ -q`
Expected: 145 passed, 0 skipped

- [ ] **Step 6: Commit**

```bash
git add config.toml README.md
git commit -m "docs: configure Wing identity alias and BoostBank owner"
```

- [ ] **Step 7: Regenerate real data and eyeball it**

The dropdown only merges identities once `metrics.json` carries the `people`
block, which requires a collector run. Either wait for the nightly CI, or refresh
locally per the README:

```bash
git -C ../ManagementDashboard-data pull
python scripts/sync_data.py
python -m http.server -d docs 8000
```

Confirm at `http://localhost:8000` that `Wing` appears **once** with **453**
tasks (375 + 78 merged), not as two entries.

**Note:** `sync_data.py` copies data produced by the *last CI run*, which used
the old collector. Until a nightly run happens with the new code, the local
`metrics.json` has no `people` key — the dropdown will then list raw authors with
`wing-csi` and `wing2036` separate. That is the documented backwards-compatible
fallback, not a bug.
