# Phase 0 — Contain & Stabilise Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the dashboard publicly re-publishing private client repo metadata every night, then fix three latent bugs and split the 1349-line frontend monolith so later phases can land safely.

**Architecture:** No new services. GitHub Pages is disabled and the publish steps removed from CI; the collector keeps running for validation only. The frontend is split from one inline-everything HTML file into a skeleton plus a stylesheet and ES modules, guarded by a rendered-HTML snapshot test that proves the split changed nothing.

**Tech Stack:** Python 3 + pytest (collector), vanilla ES modules + Chart.js 4.4.1 from CDN (frontend), GitHub Actions, Playwright via pytest (new, snapshot test only).

> **Plan location note:** saved to `plans/` at repo root, not `docs/superpowers/plans/`.
> `docs/` is the Pages artifact root (`.github/workflows/collect.yml:48`) and everything
> under it is published. Same reasoning as the spec's placement in `specs/`.

## Global Constraints

- **Spec:** `specs/2026-07-27-dashboard-enhancements-design.md` (revision 2). Phase 0 = §7 row "Phase 0".
- **Python style:** PEP 8, type annotations on all signatures, `black`/`isort`/`ruff` conventions. Existing file uses `from __future__ import annotations` and `X | None` unions — match it.
- **Test command:** `python3 -m pytest scripts/ -q` — must pass before every commit. CI runs this (`collect.yml:29-32`).
- **Commit format:** `<type>: <description>` — types `feat, fix, refactor, docs, test, chore, perf, ci`. No attribution footer.
- **File size targets:** 200–400 lines typical, 800 max.
- **Behaviour preservation:** Tasks 5–7 must not change rendered output. Tasks 4 and 8 change it deliberately and update the snapshot.
- **Never commit `docs/data/metrics.json`** after Task 1.
- **Do not read `docs/index.html:576` in full** — it is a single 80,526-byte line (`DEMO_DATA`). Use `sed -n` ranges that exclude it, or stream it.

---

### Task 1: Stop the public exposure

Highest urgency in the plan. The live file at `https://wing-csi.github.io/ManagementDashboard/data/metrics.json` regenerates nightly and contains 2,023 tasks from private repos. Removing CI steps alone does **not** stop it — Pages serves the last artifact indefinitely.

**Files:**
- Modify: `.github/workflows/collect.yml:11-14, 16-18, 23-25, 44-51`
- Create: `.gitignore`
- Manual: repo Settings → Pages

**Interfaces:**
- Consumes: nothing
- Produces: a CI workflow that collects and validates but publishes nothing.

- [ ] **Step 1: Disable GitHub Pages (manual, do this first)**

In a browser: `https://github.com/wing-csi/ManagementDashboard/settings/pages` → **Source → None** → Save.

This is the step that actually takes the URL down. Do not skip it or defer it.

- [ ] **Step 2: Verify the URL is dead**

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" https://wing-csi.github.io/ManagementDashboard/data/metrics.json
```

Expected: `HTTP 404`. If it still returns `200`, Pages is not disabled — stop and fix that before continuing. (Propagation can take a minute; retry once before investigating.)

- [ ] **Step 3: Strip publish steps from the workflow**

In `.github/workflows/collect.yml`, replace the permissions block at lines 11-14 with:

```yaml
permissions:
  contents: read
```

Delete the `concurrency` block (lines 16-18), the `environment:` block (lines 23-25), and the final three steps (lines 44-51: `configure-pages`, `upload-pages-artifact`, `deployment`). Change the collect step's output path so nothing is written into `docs/`:

```yaml
      - name: Collect metrics
        env:
          GH_METRICS_TOKEN: ${{ secrets.GH_METRICS_TOKEN || github.token }}
          BEN_GH_METRICS_TOKEN: ${{ secrets.BEN_GH_METRICS_TOKEN }}
        run: python3 scripts/collect_github.py --config config.toml --out /tmp/metrics.json
```

The run now proves the collector still works without publishing anything.

- [ ] **Step 4: Stop tracking the data file**

```bash
git rm --cached docs/data/metrics.json
printf 'docs/data/metrics.json\n' > .gitignore
```

The working copy stays on disk for local viewing; git stops tracking it.

- [ ] **Step 5: Verify tests still pass**

```bash
python3 -m pytest scripts/ -q
```

Expected: PASS (this task changes no Python).

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/collect.yml .gitignore
git commit -m "fix: stop publishing private repo metadata to public Pages

Pages disabled in repo settings; publish steps removed from CI. The
collector still runs daily to catch breakage but writes to /tmp.
metrics.json is now gitignored so it is never re-committed to the
public repo.

Dashboard is intentionally dark until the authenticated Worker ships
in Phase 1; view locally per README."
```

---

### Task 2: Make `collect_issues` report permission failures

Today a token lacking Issues:Read produces `None` with nothing in `errors` — 12 of 13 repos are silently blind (spec §2.3).

**Files:**
- Modify: `scripts/collect_github.py:780-786, 826, 875-876`
- Test: `scripts/test_collect_github.py`

**Interfaces:**
- Consumes: `CollectError` (existing), `GitHubClient.graphql`
- Produces: `collect_issues(client, repo) -> tuple[dict | None, str | None]` — `(data, error_message)`. Call sites must unpack. `repo_meta[repo]["issues_error"]` appears in `metrics.json` when collection failed.

- [ ] **Step 1: Write the failing test**

Append to `scripts/test_collect_github.py`:

```python
class RaisingClient:
    """Raises CollectError on every GraphQL call (simulates a token without Issues:Read)."""

    def __init__(self, message: str = "GraphQL error: Resource not accessible"):
        self.message = message

    def graphql(self, query: str, variables: dict, **kw) -> dict:
        raise CollectError(self.message)


def test_collect_issues_reports_permission_failure():
    data, err = collect_issues(RaisingClient(), "owner/repo")
    assert data is None
    assert err is not None
    assert "not accessible" in err


def test_collect_issues_returns_no_error_on_success():
    body = {
        "repository": {
            "openIssues": {"totalCount": 2},
            "closedIssues": {"totalCount": 1},
            "issues": {"nodes": []},
            "closedRecent": {"nodes": []},
            "milestones": {"nodes": []},
        }
    }
    data, err = collect_issues(FakeClient([body]), "owner/repo")
    assert err is None
    assert data["open_total"] == 2
    assert data["closed_total"] == 1
```

Add `collect_issues` to the import block at `scripts/test_collect_github.py:14-22`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest scripts/test_collect_github.py -k collect_issues -v`
Expected: FAIL — `TypeError: cannot unpack non-sequence NoneType` (or `ImportError` if the import line was missed).

- [ ] **Step 3: Change the return type**

In `scripts/collect_github.py`, replace lines 780-786 with:

```python
def collect_issues(client: GitHubClient, repo: str) -> tuple[dict | None, str | None]:
    """Open issues + milestone progress for the planning-side view.

    Returns (data, error). A token without Issues:Read yields (None, message)
    rather than a silent None — the dashboard must be able to say it is blind.
    """
    owner, name = repo.split("/", 1)
    try:
        data = client.graphql(ISSUES_QUERY, {"owner": owner, "name": name})
    except CollectError as e:
        return None, str(e)
```

Then change the function's closing brace at line 826 from `    }` to `    }, None` so the success path returns a 2-tuple.

- [ ] **Step 4: Update the call site**

Replace `scripts/collect_github.py:875-876` with:

```python
    if repo_classify.get("track_issues", True):
        issues, issues_err = collect_issues(client, repo)
        meta["issues"] = issues
        if issues_err:
            meta["issues_error"] = issues_err
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest scripts/ -q`
Expected: PASS, all tests.

- [ ] **Step 6: Commit**

```bash
git add scripts/collect_github.py scripts/test_collect_github.py
git commit -m "fix: surface Issues permission failures instead of swallowing them

collect_issues returned a bare None on CollectError, so 12 of 13 repos
were silently blind with nothing in errors. It now returns
(data, error) and the message lands in repo_meta[repo].issues_error."
```

---

### Task 3: Add a rendered-output snapshot harness

Tasks 5–7 must not change what the page renders. Capture a baseline first so the split is provably behaviour-preserving.

**Files:**
- Create: `scripts/test_frontend_snapshot.py`
- Create: `scripts/fixtures/metrics-fixture.json`

**Interfaces:**
- Consumes: `docs/index.html` served over HTTP
- Produces: `render_sections(page) -> dict[str, str]` mapping element id → `innerHTML`; a committed baseline at `scripts/fixtures/rendered-baseline.json` that Tasks 4–8 assert against.

- [ ] **Step 1: Install Playwright**

```bash
pip install pytest-playwright
python3 -m playwright install chromium
```

- [ ] **Step 2: Create a deterministic synthetic fixture**

Create `scripts/fixtures/metrics-fixture.json`. Small, no real client data, and it exercises the project-progress path Task 4 changes:

```json
{
 "schema_version": 2,
 "generated_at": "2026-07-20T05:00:00+00:00",
 "window_days": 180,
 "mode": "auto",
 "repos": ["acme/widget"],
 "tasks": [
  {"id": "1", "repo": "acme/widget", "branch": "main", "title": "feat: add widget",
   "author": "alice", "date": "2026-07-18", "level": "L3", "method": "label",
   "additions": 120, "deletions": 4, "lead_hours": 3.5, "kind": "pr",
   "url": "https://example.invalid/1", "rework": 0, "ci": "pass",
   "check": null, "violations": []},
  {"id": "2", "repo": "acme/widget", "branch": "main", "title": "fix: widget crash",
   "author": "bob", "date": "2026-07-19", "level": "L1", "method": "rule",
   "additions": 8, "deletions": 1, "lead_hours": null, "kind": "commit",
   "url": "https://example.invalid/2", "rework": 0, "ci": null,
   "check": null, "violations": []}
 ],
 "repo_meta": {
  "acme/widget": {
   "issues": {
    "open_total": 3, "closed_total": 7,
    "open": [
     {"number": 11, "title": "Overdue important thing", "url": "https://example.invalid/i11",
      "created": "2026-05-01", "updated": "2026-07-19", "labels": ["P0"],
      "milestone": "M1", "due": "2026-07-10", "assignees": ["alice"]},
     {"number": 12, "title": "Ordinary thing", "url": "https://example.invalid/i12",
      "created": "2026-07-15", "updated": "2026-07-19", "labels": [],
      "milestone": "M1", "due": "2026-08-30", "assignees": []},
     {"number": 13, "title": "Old bug", "url": "https://example.invalid/i13",
      "created": "2026-04-01", "updated": "2026-07-01", "labels": ["bug"],
      "milestone": null, "due": null, "assignees": []}
    ],
    "closed_recent": [],
    "milestones": [{"title": "M1", "due": "2026-07-10", "open": 2, "closed": 5}]
   }
  }
 },
 "errors": []
}
```

- [ ] **Step 3: Write the snapshot test**

Create `scripts/test_frontend_snapshot.py`:

```python
"""Rendered-output snapshot test for docs/index.html.

Proves the Phase 0 frontend split is behaviour-preserving. Regenerate the
baseline deliberately with:  pytest scripts/test_frontend_snapshot.py --snapshot-update

Run:  python3 -m pytest scripts/test_frontend_snapshot.py -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("playwright", reason="frontend snapshot test needs playwright")

DOCS = Path(__file__).parent.parent / "docs"
FIXTURES = Path(__file__).parent / "fixtures"
BASELINE = FIXTURES / "rendered-baseline.json"
PORT = 8765

SECTION_IDS = [
    "strip", "alertList", "taskRows", "projChips", "projMs",
    "projLate", "projTodo", "footStamp",
]


def pytest_addoption(parser) -> None:
    parser.addoption("--snapshot-update", action="store_true",
                     help="Rewrite the rendered baseline instead of asserting against it")


@pytest.fixture(scope="module")
def server():
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "-d", str(DOCS)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(1.5)
    yield f"http://127.0.0.1:{PORT}"
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(scope="module")
def fixture_data():
    """Swap the fixture in as docs/data/metrics.json for the duration of the test."""
    target = DOCS / "data" / "metrics.json"
    backup = DOCS / "data" / "metrics.json.snapshot-backup"
    had_original = target.exists()
    if had_original:
        shutil.move(target, backup)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / "metrics-fixture.json", target)
    yield
    target.unlink(missing_ok=True)
    if had_original:
        shutil.move(backup, target)


def render_sections(page) -> dict[str, str]:
    return {
        sid: page.eval_on_selector(f"#{sid}", "el => el.innerHTML")
        for sid in SECTION_IDS
    }


def test_rendered_output_matches_baseline(page, server, fixture_data, request):
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#taskRows tr", timeout=10_000)
    actual = render_sections(page)

    if request.config.getoption("--snapshot-update") or not BASELINE.exists():
        BASELINE.write_text(json.dumps(actual, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
        pytest.skip("baseline written")

    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    for sid in SECTION_IDS:
        assert actual[sid] == expected[sid], f"rendered output changed for #{sid}"
```

Note: `pytest_addoption` only takes effect in a root `conftest.py`. Create `scripts/conftest.py` containing just that function, and delete it from the test file:

```python
"""Pytest options shared by the scripts/ test suite."""


def pytest_addoption(parser) -> None:
    parser.addoption("--snapshot-update", action="store_true",
                     help="Rewrite the rendered baseline instead of asserting against it")
```

- [ ] **Step 4: Generate the baseline**

Run: `python3 -m pytest scripts/test_frontend_snapshot.py --snapshot-update -q`
Expected: SKIPPED with "baseline written"; `scripts/fixtures/rendered-baseline.json` now exists.

- [ ] **Step 5: Verify the baseline asserts green**

Run: `python3 -m pytest scripts/test_frontend_snapshot.py -q`
Expected: PASS.

- [ ] **Step 6: Confirm the whole suite passes**

Run: `python3 -m pytest scripts/ -q`
Expected: PASS. Where Playwright is unavailable (CI), the snapshot test self-skips via the `importorskip` at the top.

- [ ] **Step 7: Commit**

```bash
git add scripts/test_frontend_snapshot.py scripts/conftest.py scripts/fixtures/
git commit -m "test: add rendered-output snapshot harness for the frontend

Captures innerHTML of every dynamic section against a synthetic fixture
so the Phase 0 module split can be proven behaviour-preserving. Skips
where playwright is unavailable so CI stays green."
```

---

### Task 4: Fix the `issueScore` collision and its two field bugs

`issueScore` is declared twice; the second hoists over the first, so the sort at `:1151` computes `object - object` = `NaN` and the "今日建議" list renders unsorted (spec §2.4). The surviving copy is also wrong in two further ways found while planning:

- it reads `iss.milestone.due`, but `collect_issues` sets `milestone` to a **title string** with the date on a separate top-level `due` (`collect_github.py:799-800`), so due-date scoring never fires;
- it does date arithmetic against `today`, which is a **string** (`:1052`), producing `NaN`.

The dead copy at `:763-773` was field-correct and its formula is what `README.md:98` documents. Restore that formula, keep the surviving copy's `why` explanations, delete the duplicate.

**Files:**
- Modify: `docs/index.html:743-747` (delete), `:763-773` (delete), `:1033-1049` (replace), `:1151` (fix comparator)
- Test: `scripts/fixtures/rendered-baseline.json` (updated deliberately)

**Interfaces:**
- Consumes: `toDate(s)` (`:621`); pool items shaped `{number, title, url, labels[], milestone: string, due: string|null, created: string|null, updated: string|null, repo}`
- Produces: `issueScore(iss, todayStr) -> {sc: number, why: string[]}` — single declaration; callers sort on `.sc`.

- [ ] **Step 1: Delete the dead duplicate and its constant**

Delete `docs/index.html` lines 743-747 (`PRIORITY_RE`) and lines 763-773 (the first `issueScore`). Leave `issuesInScope` (`:748-762`) untouched.

- [ ] **Step 2: Replace the surviving `issueScore` with one correct implementation**

Replace `docs/index.html:1034-1049` with:

```javascript
const PRIORITY_RE = [
  [/^(p0|priority: ?(urgent|highest)|urgent|critical|blocker)$/i, 40, 'P0/critical'],
  [/^(p1|priority: ?high|high)$/i, 25, '高優先'],
  [/^(p2|priority: ?medium|medium)$/i, 10, '中優先'],
];
function issueScore(iss, todayStr) {
  let sc = 0;
  const why = [];
  const today = toDate(todayStr);
  if (iss.due) {
    const overdue = Math.round((today - toDate(iss.due)) / 864e5);
    if (overdue > 0) { sc += overdue * 3; why.push(`遲咗 ${overdue} 日`); }
  }
  for (const l of iss.labels || []) {
    for (const [re, w, label] of PRIORITY_RE) if (re.test(l)) { sc += w; why.push(label); }
    if (/^bug$/i.test(l)) { sc += 15; why.push('bug'); }
  }
  if (iss.created) {
    const age = Math.round((today - toDate(iss.created)) / 864e5);
    if (age > 0) { sc += Math.min(60, age) * 0.3; why.push(`開咗 ${age} 日`); }
  }
  return { sc, why };
}
```

This matches the formula documented at `README.md:98`: overdue days × 3, priority label 40/25/10, `bug` +15, `min(60, age) × 0.3`.

- [ ] **Step 3: Fix the comparator**

Replace `docs/index.html:1151` with:

```javascript
  const todo = [...pool].sort((a, b) => issueScore(b, today).sc - issueScore(a, today).sc).slice(0, 5);
```

- [ ] **Step 4: Verify the list is now genuinely sorted**

Run: `python3 -m pytest scripts/test_frontend_snapshot.py -q`
Expected: **FAIL** on `#projTodo` — this is the point. Fixture issue #11 is P0 and overdue (score ≈ 40 + 10×3 + age), so it must now lead; #13 (`bug`, old) second; #12 (no labels, future due) last.

If `#projTodo` did *not* change, the fix did not take effect — investigate before proceeding.

- [ ] **Step 5: Update the baseline deliberately**

```bash
python3 -m pytest scripts/test_frontend_snapshot.py --snapshot-update -q
python3 -m pytest scripts/ -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add docs/index.html scripts/fixtures/rendered-baseline.json
git commit -m "fix: today's-tasks list was rendering unsorted

issueScore was declared twice; the second hoisted over the first, so
the comparator computed object - object = NaN and the sort was a no-op.
The surviving copy also read iss.milestone.due (milestone is a title
string, the date is on iss.due) and did date arithmetic against a
string, so due-date scoring never fired either.

Single implementation now, using the formula documented in README.md:98
and returning {sc, why} for future UI explanation."
```

---

### Task 5: Extract the stylesheet

**Files:**
- Create: `docs/css/dashboard.css`
- Modify: `docs/index.html:8-351`

**Interfaces:**
- Consumes: nothing
- Produces: `docs/css/dashboard.css`, linked from `index.html`.

- [ ] **Step 1: Move the CSS out**

```bash
mkdir -p docs/css
sed -n '9,350p' docs/index.html > docs/css/dashboard.css
head -1 docs/css/dashboard.css
```

Line 8 is `<style>` and 351 is `</style>`, so the range takes only the rules. Expected first line: the Google Fonts `@import`. `@import` must precede all other rules — confirm it is line 1.

- [ ] **Step 2: Replace the inline block with a link**

In `docs/index.html`, delete lines 8-351 and insert in their place:

```html
<link rel="stylesheet" href="./css/dashboard.css">
```

- [ ] **Step 3: Verify rendered output is unchanged**

Run: `python3 -m pytest scripts/test_frontend_snapshot.py -q`
Expected: PASS. The snapshot captures `innerHTML`, not styling, so this proves the page still loads and scripts still run.

- [ ] **Step 4: Verify styling visually**

```bash
python3 -m http.server -d docs 8000
```

Open `http://localhost:8000`; confirm fonts, colours, spacing and the spectrum strip are unchanged.

- [ ] **Step 5: Commit**

```bash
git add docs/index.html docs/css/dashboard.css
git commit -m "refactor: extract dashboard stylesheet from index.html"
```

---

### Task 6: Extract the demo dataset and split the inline script

Tasks 6 and 7 of the spec's file list are combined here because the page is broken between them — `DEMO_DATA` cannot be imported until the script is a module. Execute and commit as one unit.

**Files:**
- Create: `docs/data/demo-data.js`, `docs/js/data.js`, `docs/js/aggregate.js`, `docs/js/render-kpi.js`, `docs/js/render-project.js`, `docs/js/render-table.js`, `docs/js/main.js`
- Modify: `docs/index.html` (script block → module tag)

**Interfaces:**
- Consumes: `DEMO_DATA` from `../data/demo-data.js`
- Produces:
  - `data.js` — `export const state`, `export const $`, `export const pct`, `export const esc`, `export const toDate`, `export const refDate`, `export async function loadData()`, `export function tasksBetween(fromMs, toMs)`, `export function windowTasks()`, `export function precedingTasks()`
  - `aggregate.js` — `export function issuesInScope()`, plus constants `LEVELS`, `AI_LOC_LEVELS`, `META`, `UNTAGGED_COLOR`, `INK`, `TABLE_CAP`, `FIX_RE`, `FAIL_RE`, `VIOLATION_META`, `median`, `fmtHours`
  - `render-kpi.js` — the KPI row, spectrum strip, alert and chart renderers
  - `render-project.js` — `export function renderProjects()`, `export function issueScore(iss, todayStr)`
  - `render-table.js` — the task-table renderer and `export function typeChip(t)`
  - `main.js` — `export function render()`, boot sequence, event listeners

- [ ] **Step 1: Extract the demo blob without reading it into context**

```bash
mkdir -p docs/js
sed -n '576p' docs/index.html > /tmp/demo-line.js
wc -c /tmp/demo-line.js
```

Expected: ~80,526 bytes.

- [ ] **Step 2: Convert it to a module**

```bash
{ printf 'export '; cat /tmp/demo-line.js; } > docs/data/demo-data.js
head -c 40 docs/data/demo-data.js
```

Expected first characters: `export const DEMO_DATA = {`.

- [ ] **Step 3: Remove it from index.html**

Delete lines 573-576 of `docs/index.html` (the three comment lines and the data line).

- [ ] **Step 4: Move the shared primitives**

Create `docs/js/data.js` containing, verbatim from the inline script, `state` (`:604`), `$` (`:605`), `pct` (`:606`), `esc` (`:607`), `loadData` (`:610-618`), `toDate`/`refDate` (`:621-622`) and `tasksBetween`/`windowTasks`/`precedingTasks` (`:624` onward). Add `export` before each declaration and this import at the top:

```javascript
import { DEMO_DATA } from '../data/demo-data.js';
```

- [ ] **Step 5: Move the constants and aggregation helpers**

Create `docs/js/aggregate.js` with the constants at `:578-602` and the aggregation helpers through `:741`. Add at the top:

```javascript
import { state, toDate, refDate, windowTasks, precedingTasks } from './data.js';
```

Export every symbol another module needs, per the Interfaces block.

- [ ] **Step 6: Move the renderers**

Create `docs/js/render-kpi.js`, `docs/js/render-project.js` and `docs/js/render-table.js`, moving the corresponding functions out of the remaining inline script. Each begins with only the imports it uses, e.g. for `render-project.js`:

```javascript
import { state, $, esc, toDate } from './data.js';
import { issuesInScope } from './aggregate.js';
```

`render-kpi.js` uses the global `Chart` from the CDN tag — no import, but note the dependency:

```javascript
/* Chart.js 4.4.1 is loaded globally from the CDN <script> in index.html */
```

- [ ] **Step 7: Create the entry point**

Create `docs/js/main.js` with `render()` (`:1282-1298`), the boot sequence and all event listeners, importing from the modules above.

- [ ] **Step 8: Point index.html at the entry module**

Replace the entire remaining `<script>…</script>` block with:

```html
<script type="module" src="./js/main.js"></script>
```

Keep the Chart.js CDN `<script>` tag at line 7 exactly as-is, and **before** the module tag.

- [ ] **Step 9: Verify behaviour is unchanged**

Run: `python3 -m pytest scripts/test_frontend_snapshot.py -q`
Expected: **PASS** — byte-identical rendered output for every section. Any diff means the split changed behaviour; find it before continuing.

- [ ] **Step 10: Check the browser console is clean**

```bash
python3 -m http.server -d docs 8000
```

Open `http://localhost:8000` with devtools open. Expected: no console errors, no 404s for module files, chart renders, repo/branch/window filters work, table sorts on header click.

- [ ] **Step 11: Confirm file sizes are within target**

```bash
wc -l docs/index.html docs/css/dashboard.css docs/js/*.js
```

Expected: each JS module roughly 100–400 lines; `index.html` a few hundred lines of skeleton. If any module exceeds 400 lines, split it further before committing.

- [ ] **Step 12: Commit**

```bash
git add docs/index.html docs/js/ docs/data/demo-data.js
git commit -m "refactor: split index.html into ES modules

1349-line monolith becomes a skeleton plus css/, js/ modules and an
extracted demo dataset. Behaviour-preserving: the rendered-output
snapshot is byte-identical across every section.

Local preview now needs a static server (ES modules do not run over
file://): python3 -m http.server -d docs 8000"
```

---

### Task 7: Stop `DEMO_DATA` being a silent fallback

`loadData` currently substitutes the demo blob on *any* fetch failure, flagged only by a small badge. Once auth exists in Phase 1, an expired session would render a plausible fake dashboard to a stakeholder (spec §5.4).

**Files:**
- Modify: `docs/js/data.js`, `docs/js/main.js`, `docs/index.html`
- Test: `scripts/test_frontend_snapshot.py`

**Interfaces:**
- Consumes: `DEMO_DATA`
- Produces: `loadData()` throws `LoadError` instead of silently falling back; `export class LoadError extends Error` carrying `.status`.

- [ ] **Step 1: Write the failing tests**

Add to `scripts/test_frontend_snapshot.py`:

```python
def test_missing_data_shows_error_not_demo(page, server, fixture_data):
    """A failed data fetch must show an explicit error, never silent demo data."""
    page.route("**/data/metrics.json", lambda route: route.fulfill(status=500))
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#loadError", state="visible", timeout=10_000)
    assert page.is_visible("#loadError")


def test_demo_mode_is_explicit(page, server, fixture_data):
    """?demo=1 still loads the demo dataset deliberately."""
    page.goto(f"{server}/?demo=1", wait_until="networkidle")
    page.wait_for_selector("#demoBadge", timeout=10_000)
    assert page.is_visible("#demoBadge")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest scripts/test_frontend_snapshot.py -k "error_not_demo or demo_mode" -v`
Expected: FAIL — `#loadError` does not exist yet.

- [ ] **Step 3: Rewrite `loadData`**

In `docs/js/data.js`:

```javascript
export class LoadError extends Error {
  constructor(status) {
    super(`metrics fetch failed: ${status}`);
    this.name = 'LoadError';
    this.status = status;
  }
}

export async function loadData() {
  if (new URLSearchParams(location.search).get('demo') === '1') {
    return { data: DEMO_DATA, demo: true };
  }
  const res = await fetch('./data/metrics.json', { cache: 'no-store' });
  if (!res.ok) throw new LoadError(res.status);
  return { data: await res.json(), demo: false };
}
```

- [ ] **Step 4: Add the error element**

In `docs/index.html`, immediately inside the main container, add:

```html
<div id="loadError" hidden role="alert" class="card">
  <strong>載入數據失敗。</strong>
  <span id="loadErrorDetail"></span>
  <div style="margin-top:6px;color:var(--muted);font-size:12px">
    未登入或者 session 過期?<a href="./">重新登入</a>。想睇示範數據:<a href="./?demo=1">?demo=1</a>
  </div>
</div>
```

- [ ] **Step 5: Handle the error at boot**

In `docs/js/main.js`:

```javascript
import { state, $, loadData, LoadError } from './data.js';

try {
  const { data, demo } = await loadData();
  state.data = data;
  state.demo = demo;
  render();
} catch (e) {
  const box = $('loadError');
  box.hidden = false;
  $('loadErrorDetail').textContent =
    e instanceof LoadError && e.status === 401
      ? '需要登入。'
      : `(${e instanceof LoadError ? e.status : 'network'})`;
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m pytest scripts/ -q`
Expected: PASS.

- [ ] **Step 7: Verify the happy path is untouched**

Run: `python3 -m pytest scripts/test_frontend_snapshot.py -q`
Expected: PASS — the baseline is unchanged, because a successful load behaves exactly as before.

- [ ] **Step 8: Commit**

```bash
git add docs/js/data.js docs/js/main.js docs/index.html scripts/test_frontend_snapshot.py
git commit -m "fix: never silently substitute demo data for real metrics

loadData fell back to the demo dataset on any fetch failure, flagged
only by a small badge. After Phase 1 an expired session would have
rendered a plausible fake dashboard to a stakeholder. Demo data now
loads only via explicit ?demo=1; anything else shows an error state."
```

---

### Task 8: Update documentation

**Files:**
- Modify: `README.md:277-291` (Private 模式), `:314-322` (本地跑), `:330`

**Interfaces:**
- Consumes: nothing
- Produces: a README matching reality.

- [ ] **Step 1: Correct the hosting section**

In `README.md`, replace the Private 模式 guidance with the current state: Pages is disabled, the collector runs daily for validation only, and the dashboard is viewed locally until the authenticated Worker ships in Phase 1. Include the local flow verbatim:

```bash
export GH_METRICS_TOKEN=github_pat_xxx
python3 scripts/collect_github.py --config config.toml --out docs/data/metrics.json
python3 -m http.server -d docs 8000   # http://localhost:8000
```

State explicitly that opening `index.html` via `file://` no longer works, because ES modules require a server.

- [ ] **Step 2: Note the gitignore**

Add one line stating `docs/data/metrics.json` is gitignored and must never be committed to this public repo.

- [ ] **Step 3: Remove the now-false Pages guidance**

Line 330 currently tells the reader to make the hub repo public so Pages works. Delete it — Pages is off and that advice caused the exposure.

- [ ] **Step 4: Verify commands are copy-pasteable**

Re-read the edited sections; confirm every command runs and every claim matches what the code now does.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: update hosting and local-run instructions for Phase 0"
```

---

## Self-Review

**Spec coverage.** Every Phase 0 item in spec §7 maps to a task: disable Pages + strip deploy steps + gitignore → Task 1; `collect_issues` errors → Task 2; `issueScore` fix → Task 4; frontend split → Tasks 5–6; DEMO_DATA fallback → Task 7. Tasks 3 and 8 are supporting work (regression safety, docs) the spec implies but does not enumerate.

**Deliberate additions beyond the spec.** Task 3's snapshot harness is not in the spec; without it "behaviour-preserving" (spec §5.4) is unverifiable. Task 4 fixes two field bugs found during planning — `iss.milestone.due` against a string field, and date arithmetic against a string — that the spec did not know about. The spec said only "keep the object-returning version", which would have preserved both.

**Ordering constraint.** The demo-data extraction leaves the page broken until the module split completes; both live in Task 6 and commit as one unit.

**Type consistency check.** `issueScore` returns `{sc, why}` in Task 4 and is consumed as `.sc` at the call site in the same task, and re-exported unchanged in Task 6. `collect_issues` returns a 2-tuple in Task 2 and is unpacked at its single call site in the same task. `loadData` returns `{data, demo}` throughout and additionally throws `LoadError` from Task 7.

**Not covered here, by design.** Purging historical `metrics.json` blobs from git history (spec §10) and anything requiring Cloudflare or the GitHub App (Phase 1).
