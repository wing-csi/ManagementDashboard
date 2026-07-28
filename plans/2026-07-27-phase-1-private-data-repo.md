# Phase 1 — Private Data Repo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore automatic nightly data refresh, with the data gated behind GitHub repository permissions instead of published to the public web.

**Architecture:** The public repo keeps all code. A **separate private repo** receives `metrics.json` nightly, pushed by GitHub Actions using a least-privilege PAT. Viewers clone both repos and `git pull` to refresh. Access control is GitHub repo permission — there is no login page and no hosted URL, because GitHub free/Pro cannot authenticate a static site. **No third-party services of any kind.**

**Tech Stack:** GitHub Actions, two GitHub repos, Python 3 + pytest. Nothing else.

```
  PUBLIC  wing-csi/ManagementDashboard          ─ code, config, frontend
     │  Actions (daily 05:00 HKT) collects, then pushes with DATA_REPO_PAT
     ▼
  PRIVATE wing-csi/ManagementDashboard-data     ─ metrics.json only
     │  git pull
     ▼
  viewer (collaborator on the data repo) ─ scripts/sync_data.py ─ local server
```

## Context for someone with zero prior knowledge

This project is a metrics dashboard. A Python collector reads GitHub data for ~13
tracked repos and writes `metrics.json`; a static frontend renders it.

**Why this phase exists.** The dashboard used to publish `metrics.json` to GitHub Pages.
That file contains commit titles, author logins and branch names for tracked repos —
most of which are **private client repos**. It was world-readable and refreshing nightly.
Phase 0 (already shipped, commits `106bb63`..`10839bf`) removed the publishing pipeline,
which stopped the bleeding but left the collector writing to `/tmp` and throwing the
output away. Refreshing the dashboard is currently a manual chore.

Phase 1 restores automation without restoring the leak.

**Read before starting:** `specs/2026-07-27-dashboard-enhancements-design.md` §5.1, §5.2,
§5.5, and §6 "#1". Especially §5.5, which records honestly what this model *cannot* do.

## Global Constraints

- **Spec:** `specs/2026-07-27-dashboard-enhancements-design.md` **revision 3**. Phase 1 = §7 row "1 — Private data repo".
- **No third-party services.** Hard user constraint. No Cloudflare, no external identity provider, no hosting platform. If a step seems to need one, stop and report — do not improvise.
- **Python style:** PEP 8, type annotations on all signatures, `from __future__ import annotations`, `X | None` unions. Match `scripts/collect_github.py`.
- **Test command:** `python3 -m pytest scripts/ -q` — must pass before every commit. Baseline is **85 passed** before this plan starts.
- **Commit format:** `<type>: <description>` — types `feat, fix, refactor, docs, test, chore, perf, ci`. **No attribution or co-author footer.**
- **File size targets:** 200–400 lines typical, 800 max.
- **`docs/data/metrics.json` must stay gitignored and untracked in this public repo.** This is the single most important invariant in the project. A test guards it.
- **Never print, echo, or log the value of `DATA_REPO_PAT`** or any token.
- **Do not read `docs/data/demo-data.js`** — it is one 80,526-byte line and will overflow your context.
- **Exact names used throughout:** public repo `wing-csi/ManagementDashboard`; private data repo `wing-csi/ManagementDashboard-data`; secret name `DATA_REPO_PAT`.

---

## Prerequisites — human actions, before Task 1

These cannot be done by an agent: they require the GitHub web UI and handling a
credential. **Do not start Task 1 until all of P1–P4 verify.**

- [ ] **P1. Create the private data repo.** At https://github.com/new create
  **`ManagementDashboard-data`** under the `wing-csi` account, visibility **Private**,
  and tick "Add a README file" so the repo has an initial commit on `main` (an empty
  repo has no branch to push to and the workflow will fail).

- [ ] **P2. Create a fine-grained PAT.** At
  https://github.com/settings/personal-access-tokens/new
  - Repository access: **Only select repositories** → `ManagementDashboard-data` **only**
  - Permissions → Repository permissions → **Contents: Read and write**
  - Set an expiry you will actually renew, and diarise it — when it expires the nightly
    push fails silently from your point of view (the workflow run goes red, but nobody
    is watching it).

- [ ] **P3. Add it as a secret on the PUBLIC repo.** At
  https://github.com/wing-csi/ManagementDashboard/settings/secrets/actions →
  New repository secret → name exactly **`DATA_REPO_PAT`**, value = the token from P2.

- [ ] **P4. Verify the data repo really is private.** Logged out (or in a private
  browser window), open
  `https://github.com/wing-csi/ManagementDashboard-data` — it must show **404**.
  If it renders, it is public: fix that before continuing, or Phase 1 recreates the leak
  in a new location.

- [ ] **P5. (Separate, still outstanding from Phase 0) Disable GitHub Pages.** At
  https://github.com/wing-csi/ManagementDashboard/settings/pages → **Source: None**.
  Then verify:
  ```bash
  curl -s -o /dev/null -w "%{http_code}\n" https://wing-csi.github.io/ManagementDashboard/data/metrics.json
  ```
  Expect **404**. If it returns **200**, the previously published snapshot of private
  client data is still world-readable. Phase 1 does **not** fix this — Phase 1 stops
  *future* data reaching the public, but the already-published artifact stays up until
  Pages is switched off.

---

### Task 1: Guard the pipeline with tests, then publish to the data repo

Written test-first: the regression guards must exist and pass *before* the workflow is
changed, so they genuinely protect the invariant rather than being written to fit
whatever was built.

**Files:**
- Create: `scripts/test_workflow_publish.py`
- Modify: `.github/workflows/collect.yml`

**Interfaces:**
- Consumes: `/tmp/metrics.json`, written by the existing "Collect metrics" step
- Produces: `metrics.json` on the default branch of `wing-csi/ManagementDashboard-data`, refreshed nightly

- [ ] **Step 1: Write the guard tests**

Create `scripts/test_workflow_publish.py`:

```python
"""Regression guards for the CI data pipeline.

The original incident: metrics.json (containing private client repo metadata) was
published to public GitHub Pages and committed to a public repo. Phase 0 removed that;
Phase 1 replaces it with a push to a PRIVATE data repo. These tests make it hard to
silently regress into publishing from the public repo again.

Run:  python3 -m pytest scripts/test_workflow_publish.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "collect.yml"
GITIGNORE = ROOT / ".gitignore"
DATA_REPO = "wing-csi/ManagementDashboard-data"
PUBLISH_STEP = "Publish metrics to private data repo"
CHECKOUT_STEP = "Checkout private data repo"


# --- dependency-free guards: these must never skip ---------------------------

def test_metrics_json_stays_gitignored() -> None:
    """The original leak was metrics.json tracked in a public repo. Never again."""
    assert "docs/data/metrics.json" in GITIGNORE.read_text(encoding="utf-8")


def test_workflow_has_no_pages_publishing() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    for forbidden in ("configure-pages", "upload-pages-artifact", "deploy-pages"):
        assert forbidden not in text, f"Pages publishing step {forbidden!r} is back"


def test_collector_writes_outside_the_repo() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "--out /tmp/metrics.json" in text
    assert "--out docs/data/metrics.json" not in text


def test_token_is_never_interpolated_into_a_shell_string() -> None:
    """A token in a URL or echo can leak via set -x, error output, or a crash dump."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "echo ${{ secrets.DATA_REPO_PAT }}" not in text
    assert "x-access-token:${" not in text, "put the PAT in actions/checkout, not a URL"


# --- structural guards: need PyYAML (installed by the workflow's test step) ---

yaml = pytest.importorskip("yaml", reason="PyYAML needed for workflow structure tests")


def _steps() -> list[dict]:
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    (job,) = wf["jobs"].values()
    return job["steps"]


def _step(name: str) -> dict:
    for s in _steps():
        if s.get("name") == name:
            return s
    pytest.fail(f"workflow step {name!r} not found")


def test_workflow_token_stays_read_only() -> None:
    """The job pushes with a PAT, so the workflow's own token needs no write access."""
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert wf["permissions"] == {"contents": "read"}


def test_data_repo_checkout_targets_the_private_repo() -> None:
    step = _step(CHECKOUT_STEP)
    assert step["with"]["repository"] == DATA_REPO
    assert step["with"]["token"] == "${{ secrets.DATA_REPO_PAT }}"
    assert step["with"]["path"] == "data-repo"


def test_publish_steps_are_guarded_against_pull_requests() -> None:
    """Fork PRs cannot read secrets; an unguarded push step fails on every PR."""
    guard = "github.event_name != 'pull_request'"
    for name in (CHECKOUT_STEP, PUBLISH_STEP):
        assert guard in _step(name)["if"], f"{name} is missing the pull_request guard"


def test_publish_step_pushes_from_the_data_repo_only() -> None:
    step = _step(PUBLISH_STEP)
    assert step["working-directory"] == "data-repo"
    assert "git push" in step["run"]
```

- [ ] **Step 2: Run the tests and confirm which fail**

Run: `python3 -m pytest scripts/test_workflow_publish.py -v`

Expected RED state: the four dependency-free tests **PASS** (Phase 0 already satisfies
them), `test_workflow_token_stays_read_only` **PASSES**, and the three referring to the
checkout/publish steps **FAIL** with "workflow step … not found", because those steps do
not exist yet.

If any of the four dependency-free tests fails, **stop** — something regressed in Phase 0
and must be understood before adding a publish pipeline on top of it.

- [ ] **Step 3: Add the publish steps to the workflow**

In `.github/workflows/collect.yml`, append these two steps after the existing
"Collect metrics" step (which stays exactly as it is):

```yaml
      - name: Checkout private data repo
        if: github.event_name != 'pull_request'
        uses: actions/checkout@v4
        with:
          repository: wing-csi/ManagementDashboard-data
          token: ${{ secrets.DATA_REPO_PAT }}
          path: data-repo

      - name: Publish metrics to private data repo
        if: github.event_name != 'pull_request'
        working-directory: data-repo
        run: |
          cp /tmp/metrics.json metrics.json
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add metrics.json
          if git diff --staged --quiet; then
            echo "metrics unchanged — nothing to publish"
          else
            git commit -m "chore: update metrics"
            git push
          fi
```

The `if git diff --staged --quiet` guard matters: without it, a run where nothing
changed fails on an empty commit.

In the same file, add PyYAML to the test step so the structural guards actually run in
CI rather than skipping:

```yaml
      - name: Run tests
        run: |
          pip install pytest pyyaml -q
          python3 -m pytest scripts/ -q
```

And rename the job, whose current name `collect-deploy` is now actively wrong — nothing
deploys any more:

```yaml
jobs:
  collect-publish:
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `python3 -m pytest scripts/ -q`
Expected: **93 passed** (85 existing + 8 new).

- [ ] **Step 5: Commit**

```bash
git add scripts/test_workflow_publish.py .github/workflows/collect.yml
git commit -m "feat: publish metrics to a private data repo

Restores nightly refresh without restoring the leak. Actions pushes
metrics.json to wing-csi/ManagementDashboard-data, a private repo, using
a fine-grained PAT scoped to Contents:write on that repo only. The
workflow's own token stays contents:read.

Adds regression guards so the pipeline cannot silently revert to
publishing from the public repo: metrics.json must stay gitignored, no
Pages steps may reappear, the collector must write outside the repo, and
the PAT must never be interpolated into a shell string."
```

---

### Task 2: A helper to wire pulled data into the dashboard

The frontend always reads `docs/data/metrics.json`, which is gitignored here. The real
file arrives via a clone of the data repo. This bridges them, cross-platform, so the
README does not need different `cp` syntax for PowerShell and bash.

**Files:**
- Create: `scripts/sync_data.py`
- Create: `scripts/test_sync_data.py`

**Interfaces:**
- Consumes: a local clone of `ManagementDashboard-data`
- Produces: `sync_data.resolve_source(data_repo: Path) -> Path` and `sync_data.sync(src: Path, dest: Path) -> int` (returns bytes written); CLI `python3 scripts/sync_data.py [--from PATH]`

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_sync_data.py`:

```python
"""Tests for scripts/sync_data.py.

Run:  python3 -m pytest scripts/test_sync_data.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from sync_data import resolve_source, sync  # noqa: E402

SAMPLE = '{"schema_version": 2, "generated_at": "2026-07-20T05:00:00+00:00", "tasks": []}'


def test_resolve_source_finds_metrics_in_a_data_repo_clone(tmp_path: Path) -> None:
    repo = tmp_path / "ManagementDashboard-data"
    repo.mkdir()
    (repo / "metrics.json").write_text(SAMPLE, encoding="utf-8")
    assert resolve_source(repo) == repo / "metrics.json"


def test_resolve_source_explains_a_missing_clone(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError) as exc:
        resolve_source(tmp_path / "nope")
    assert "clone" in str(exc.value).lower()


def test_resolve_source_explains_an_empty_clone(tmp_path: Path) -> None:
    """A clone that exists but has no metrics.json means CI has not pushed yet."""
    repo = tmp_path / "ManagementDashboard-data"
    repo.mkdir()
    with pytest.raises(FileNotFoundError) as exc:
        resolve_source(repo)
    assert "metrics.json" in str(exc.value)


def test_sync_copies_content_and_creates_the_destination_dir(tmp_path: Path) -> None:
    src = tmp_path / "metrics.json"
    src.write_text(SAMPLE, encoding="utf-8")
    dest = tmp_path / "docs" / "data" / "metrics.json"
    written = sync(src, dest)
    assert dest.read_text(encoding="utf-8") == SAMPLE
    assert written == len(SAMPLE.encode("utf-8"))


def test_sync_overwrites_an_existing_stale_file(tmp_path: Path) -> None:
    src = tmp_path / "metrics.json"
    src.write_text(SAMPLE, encoding="utf-8")
    dest = tmp_path / "docs" / "data" / "metrics.json"
    dest.parent.mkdir(parents=True)
    dest.write_text('{"stale": true}', encoding="utf-8")
    sync(src, dest)
    assert dest.read_text(encoding="utf-8") == SAMPLE
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest scripts/test_sync_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sync_data'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/sync_data.py`:

```python
#!/usr/bin/env python3
"""Copy metrics.json from a clone of the private data repo into docs/data/.

The dashboard always reads docs/data/metrics.json. In this public repo that path is
gitignored — the real data lives in the private repo wing-csi/ManagementDashboard-data,
which CI refreshes nightly. This script bridges the two, so the documented workflow is
identical on Windows, macOS and Linux.

Usage:
    python3 scripts/sync_data.py                     # ../ManagementDashboard-data
    python3 scripts/sync_data.py --from /path/to/ManagementDashboard-data
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_REPO = REPO_ROOT.parent / "ManagementDashboard-data"
DEST = REPO_ROOT / "docs" / "data" / "metrics.json"


def resolve_source(data_repo: Path) -> Path:
    """Locate metrics.json inside a data-repo clone, or explain what is missing."""
    if not data_repo.is_dir():
        raise FileNotFoundError(
            f"No data repo at {data_repo}.\n"
            f"Clone it next to this repo:\n"
            f"  git clone https://github.com/wing-csi/ManagementDashboard-data.git "
            f"{data_repo}\n"
            f"(You need to be a collaborator on that private repo.)"
        )
    src = data_repo / "metrics.json"
    if not src.is_file():
        raise FileNotFoundError(
            f"{data_repo} has no metrics.json yet.\n"
            f"Run 'git pull' there. If it is still missing, the nightly collect "
            f"workflow has not published successfully — check the Actions tab."
        )
    return src


def sync(src: Path, dest: Path) -> int:
    """Copy src over dest, creating parent directories. Returns bytes written."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return dest.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from", dest="data_repo", type=Path, default=DEFAULT_DATA_REPO,
        help="path to a clone of ManagementDashboard-data "
             "(default: ../ManagementDashboard-data)",
    )
    args = parser.parse_args()
    try:
        src = resolve_source(args.data_repo)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    written = sync(src, DEST)
    print(f"synced {written:,} bytes -> {DEST.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest scripts/ -q`
Expected: **98 passed** (93 + 5 new).

- [ ] **Step 5: Confirm the CLI fails gracefully when the clone is absent**

```bash
python3 scripts/sync_data.py --from /tmp/definitely-not-here
echo "exit status: $?"
```

Expected: exit status **1** and a message telling you to clone the repo — **not** a
Python traceback.

- [ ] **Step 6: Commit**

```bash
git add scripts/sync_data.py scripts/test_sync_data.py
git commit -m "feat: add sync_data helper for the private data repo

The dashboard reads docs/data/metrics.json, which is gitignored here.
This copies it from a clone of the private data repo, with actionable
errors when the clone is missing or has not been pulled yet, and one
documented command that works on Windows and Unix alike."
```

---

### Task 3: Rewrite the run instructions

**Files:**
- Modify: `README.md` — the `## Private 模式` and `## 本地跑` sections

**Interfaces:**
- Consumes: nothing
- Produces: instructions that match the Phase 1 pipeline

- [ ] **Step 1: Read the current sections**

```bash
grep -n '^## ' README.md
```

Read `## Private 模式` and `## 本地跑` in full before editing. The README is written in
Cantonese — **match that register and terminology**; do not switch to English prose.
Keep commands and code blocks as they are.

- [ ] **Step 2: Rewrite them to describe the two-repo flow**

The instructions must convey, accurately:

1. Data lives in the **private** repo `wing-csi/ManagementDashboard-data`; you must be a
   collaborator on it. Ask the maintainer for access.
2. First-time setup — clone it **next to** this repo:
   ```bash
   git clone https://github.com/wing-csi/ManagementDashboard-data.git ../ManagementDashboard-data
   ```
3. Everyday refresh — three commands:
   ```bash
   git -C ../ManagementDashboard-data pull
   python3 scripts/sync_data.py
   python3 -m http.server -d docs 8000   # http://localhost:8000
   ```
4. **`file://` does not work** — the frontend uses ES modules, which browsers block over
   the file protocol. A static server is required.
5. You no longer need to run the collector by hand; CI refreshes the data repo nightly
   at 05:00 HKT. Running it manually is still supported when you want data fresher than
   the last nightly run, and still needs `GH_METRICS_TOKEN` (plus `BEN_GH_METRICS_TOKEN`
   for the `benegg` repos).
6. `docs/data/metrics.json` stays gitignored in this public repo and must never be
   committed.

- [ ] **Step 3: Verify every command actually works**

Run each command from Step 2 yourself, in order, and confirm the dashboard renders at
`http://localhost:8000`. If you do not have access to the private data repo, say so in
your report rather than marking this verified — an unverified instruction block is how
documentation rots.

- [ ] **Step 4: Confirm no stale claims remain**

```bash
grep -n -i 'pages\|worker\|cloudflare' README.md
```

Every remaining hit must be either an explanation that Pages is deliberately unused, or
unrelated (e.g. `MAX_PAGES`). **No instruction may tell a reader to enable Pages** —
that is what caused the original leak.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document the private data repo workflow

Clone the data repo alongside, git pull, sync_data.py, serve. Replaces
the interim 'run the collector yourself' instructions from Phase 0."
```

---

### Task 4: End-to-end verification

Everything so far is local. This proves the real pipeline works and, more importantly,
that it does not leak.

**Files:** none — verification only.

**Interfaces:**
- Consumes: the merged work of Tasks 1–3
- Produces: evidence the pipeline is live and the data is not public

- [ ] **Step 1: Push and trigger a real run**

```bash
git push
```

Then at https://github.com/wing-csi/ManagementDashboard/actions/workflows/collect.yml →
**Run workflow**.

- [ ] **Step 2: Confirm the run succeeded and published**

Watch the run; all steps must be green. Open the "Publish metrics to private data repo"
step's log and confirm it either committed or printed
`metrics unchanged — nothing to publish`.

If the checkout step fails with a 404 or permission error, `DATA_REPO_PAT` is wrong or
lacks Contents:write on the data repo — revisit prerequisites P2/P3.

- [ ] **Step 3: Confirm the data landed**

```bash
git -C ../ManagementDashboard-data pull
python3 -c "import json;d=json.load(open('../ManagementDashboard-data/metrics.json',encoding='utf-8'));print('generated_at:',d['generated_at']);print('tasks:',len(d['tasks']))"
```

Expected: a `generated_at` from today, and a non-zero task count.

- [ ] **Step 4: Confirm the data is NOT public — the point of the whole phase**

```bash
curl -s -o /dev/null -w "data repo raw   -> HTTP %{http_code}\n" https://raw.githubusercontent.com/wing-csi/ManagementDashboard-data/main/metrics.json
curl -s -o /dev/null -w "public repo raw -> HTTP %{http_code}\n" https://raw.githubusercontent.com/wing-csi/ManagementDashboard/main/docs/data/metrics.json
curl -s -o /dev/null -w "pages           -> HTTP %{http_code}\n" https://wing-csi.github.io/ManagementDashboard/data/metrics.json
```

Required: **404 on all three.** `raw.githubusercontent.com` is anonymous, so a 200 on the
first line means the data repo is public — stop and fix it immediately.

If the third line returns 200, GitHub Pages is still enabled — prerequisite P5 is
outstanding and the original exposure is still live.

- [ ] **Step 5: Confirm the dashboard renders from pulled data**

```bash
python3 scripts/sync_data.py
python3 -m http.server -d docs 8000
```

Open `http://localhost:8000`. Confirm the header timestamp matches today's collection,
the KPI row is populated, and the browser console shows no errors.

- [ ] **Step 6: Confirm the public repo is still clean**

```bash
git status --porcelain
git ls-files docs/data/metrics.json
```

Expected: `git status` prints nothing (the synced file is gitignored) and `git ls-files`
prints nothing (it is untracked). If either shows the file, the leak is being recreated
— stop.

- [ ] **Step 7: Record the outcome**

No commit. Report: the workflow run URL, the three curl results, the `generated_at` you
observed, and whether P5 (Pages) is still outstanding.

---

## Self-Review

**Spec coverage.** Spec §6 "#1" lists five deliverables: the private data repo
(prerequisite P1), the least-privilege PAT (P2/P3), the workflow push step (Task 1), the
local wiring step (Task 2), and the README rewrite (Task 3). Its testing paragraph asks
for a guard on the push step, a gitignore regression guard, and a manual check that the
data repo is private — Task 1 Step 1 and Task 4 Step 4 cover all three.

**Deliberate deviation.** The spec's local wiring says "simplest is a documented
`cp`/symlink". This plan writes `scripts/sync_data.py` instead, because the maintainer
works on Windows and `cp`/`ln -s` do not translate to PowerShell — one tested script
keeps the README to a single command per platform, and its error messages guide a viewer
who has not been granted data-repo access yet.

**Out of scope, by design.** `history.json` (spec §6 "#6") belongs to Phase 3 — the
publish step here handles `metrics.json` only, and extending it later is a one-line
change. Nothing in this plan touches the collector, the frontend, or the metric
definitions.

**Type consistency.** `resolve_source(data_repo: Path) -> Path` and
`sync(src: Path, dest: Path) -> int` are defined in Task 2 Step 3 and consumed by the
tests in Task 2 Step 1 and by `main()` in the same file. No other task references them.

**Known risk this plan does not remove.** The PAT expires. When it does, the nightly push
fails and the data silently stops refreshing — the dashboard shows stale numbers with no
visible error, which is exactly the symptom that prompted this phase. Diarise the expiry.
A future phase could surface a staleness warning when `generated_at` is more than ~2 days
old.

**Still outstanding from Phase 0.** Disabling GitHub Pages (prerequisite P5). Phase 1
does not close the original exposure — it prevents new data reaching the public, but the
last published artifact remains until Pages is switched off.
