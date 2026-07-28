# Phase 2 — Cloudflare Pages + Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Task 3 requires the human user (Cloudflare dashboard clicks) — do not attempt it with a subagent.

**Goal:** Host the dashboard at `https://management-dashboard-emj.pages.dev` behind Cloudflare Access (email one-time PIN, 3-address allowlist), refreshed by the existing nightly CI.

**Architecture:** The existing `collect.yml` gains one final step that copies the freshly collected `metrics.json` into the runner's `docs/data/` and direct-uploads `docs/` to a Cloudflare Pages project with `wrangler`. Access protects the whole hostname; the frontend is unchanged. See `specs/2026-07-28-phase-2-cloudflare-pages-access-design.md` (approved).

**Tech Stack:** GitHub Actions, wrangler v4 (via npx, no repo dependency), Cloudflare Pages + Zero Trust Access, Python 3 + pytest for workflow guard tests.

## Global Constraints

- **Spec:** `specs/2026-07-28-phase-2-cloudflare-pages-access-design.md`. It supersedes the Phase 1 "no third-party services" constraint — Cloudflare is now explicitly in scope.
- **Ordering (security):** the first CI deploy contains real `metrics.json`. Cloudflare Access must be set up and verified blocking (Task 3) **before** the CI change is pushed to GitHub and before secrets are set (Task 4). Tasks 1–2 commit locally only; nothing is pushed until Task 4.
- **Test command:** `python3 -m pytest scripts/ -q` — must pass before every commit.
- **Commit format:** `<type>: <description>` — types `feat, fix, refactor, docs, test, chore, perf, ci`. **No attribution or co-author footer.**
- **`docs/data/metrics.json` must stay gitignored and untracked in this public repo.** The deploy step copies it inside the CI runner only, never `git add`s it.
- **Never print, echo, or log the value of any secret** (`CLOUDFLARE_API_TOKEN`, `DATA_REPO_PAT`, `GH_METRICS_TOKEN`). The agent never handles the Cloudflare token value at all — the user pastes it into GitHub themselves.
- **Do not read `docs/data/demo-data.js`** — one 80,526-byte line, will overflow context.
- **Exact names:** Pages project `management-dashboard`; workflow step `Deploy dashboard to Cloudflare Pages`; secrets `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`; allowlist emails `wingpoon1990@gmail.com`, `wing.poon@chinasofti.com`, `Shane.chan@chinasofti.com`.

## Context for someone with zero prior knowledge

This repo collects GitHub metrics for ~13 tracked repos nightly (05:00 HKT) via
`.github/workflows/collect.yml`: it runs tests, runs the collector to `/tmp/metrics.json`,
and pushes that file to a **private** data repo (`wing-csi/ManagementDashboard-data`).
The static dashboard in `docs/` renders `docs/data/metrics.json` (gitignored here,
because it contains private client repo commit titles — it leaked once via GitHub Pages;
`scripts/test_workflow_publish.py` guards against regressions).

Phase 2 adds a second consumer of the same nightly run: a Cloudflare Pages deploy,
gated by Cloudflare Access so only three named emails can view it.

---

### Task 1: Cloudflare deploy step in collect.yml (TDD)

**Files:**
- Create: `scripts/test_workflow_deploy.py`
- Modify: `.github/workflows/collect.yml` (append one step after `Publish metrics to private data repo`)

**Interfaces:**
- Consumes: existing workflow steps `Collect metrics` (writes `/tmp/metrics.json`) and `Publish metrics to private data repo` (step-name string reused in an ordering test).
- Produces: workflow step named exactly `Deploy dashboard to Cloudflare Pages`; expects GitHub secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` (set in Task 3 M6).

- [ ] **Step 1: Write the failing guard tests**

Create `scripts/test_workflow_deploy.py` (mirrors the style of `scripts/test_workflow_publish.py`):

```python
"""Guards for the Cloudflare Pages deploy step added in Phase 2.

Phase 2 hosts the dashboard (including the private metrics.json) on Cloudflare
Pages behind Cloudflare Access. These tests pin the safety properties of the
deploy step: fail loudly when secrets are missing, never leak the token into a
shell string, never commit metrics.json, and only deploy after the data-repo
publish has completed.

Run:  python3 -m pytest scripts/test_workflow_deploy.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "collect.yml"
DEPLOY_STEP = "Deploy dashboard to Cloudflare Pages"
PUBLISH_STEP = "Publish metrics to private data repo"


# --- dependency-free guards: these must never skip ---------------------------

def test_deploy_uses_pinned_wrangler_and_exact_project() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "wrangler@4 pages deploy docs" in text
    assert "--project-name=management-dashboard" in text
    assert "--branch=main" in text


def test_deploy_token_is_never_interpolated_into_a_shell_string() -> None:
    """The token must reach wrangler via env:, not inline ${{ }} in run lines."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "echo ${{ secrets.CLOUDFLARE_API_TOKEN }}" not in text
    for line in text.splitlines():
        if "wrangler" in line:
            assert "${{" not in line, f"secret interpolated into shell line: {line!r}"


# --- structural guards: need PyYAML — they skip without it -------------------

def _steps() -> list[dict]:
    yaml = pytest.importorskip("yaml", reason="PyYAML needed for workflow structure tests")
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    (job,) = wf["jobs"].values()
    return job["steps"]


def _step(name: str) -> dict:
    for s in _steps():
        if s.get("name") == name:
            return s
    pytest.fail(f"workflow step {name!r} not found")


def test_deploy_step_is_guarded_against_pull_requests() -> None:
    """Fork PRs cannot read secrets; an unguarded deploy step fails on every PR."""
    assert "github.event_name != 'pull_request'" in _step(DEPLOY_STEP)["if"]


def test_deploy_step_passes_secrets_via_env() -> None:
    env = _step(DEPLOY_STEP)["env"]
    assert env["CLOUDFLARE_API_TOKEN"] == "${{ secrets.CLOUDFLARE_API_TOKEN }}"
    assert env["CLOUDFLARE_ACCOUNT_ID"] == "${{ secrets.CLOUDFLARE_ACCOUNT_ID }}"


def test_deploy_step_fails_loudly_when_secrets_missing() -> None:
    """Spec: missing secrets must be an explicit CI failure, never a silent skip."""
    run = _step(DEPLOY_STEP)["run"]
    assert 'if [ -z "$CLOUDFLARE_API_TOKEN" ]' in run
    assert 'if [ -z "$CLOUDFLARE_ACCOUNT_ID" ]' in run
    assert "exit 1" in run


def test_deploy_copies_metrics_into_the_runner_workspace_only() -> None:
    run = _step(DEPLOY_STEP)["run"]
    assert "cp /tmp/metrics.json docs/data/metrics.json" in run
    assert "git add" not in run, "metrics.json must never be committed to this repo"


def test_deploy_runs_after_the_data_repo_publish() -> None:
    names = [s.get("name") for s in _steps()]
    assert names.index(DEPLOY_STEP) > names.index(PUBLISH_STEP)
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python3 -m pytest scripts/test_workflow_deploy.py -v`
Expected: FAIL — the two text guards fail on missing strings; the structural guards fail with `workflow step 'Deploy dashboard to Cloudflare Pages' not found`.

- [ ] **Step 3: Append the deploy step to collect.yml**

Append after the `Publish metrics to private data repo` step (same indentation as sibling steps):

```yaml
      - name: Deploy dashboard to Cloudflare Pages
        if: github.event_name != 'pull_request'
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
        run: |
          if [ -z "$CLOUDFLARE_API_TOKEN" ]; then
            echo "::error::CLOUDFLARE_API_TOKEN secret is not set — cannot deploy to Cloudflare Pages"
            exit 1
          fi
          if [ -z "$CLOUDFLARE_ACCOUNT_ID" ]; then
            echo "::error::CLOUDFLARE_ACCOUNT_ID secret is not set — cannot deploy to Cloudflare Pages"
            exit 1
          fi
          cp /tmp/metrics.json docs/data/metrics.json
          npx --yes wrangler@4 pages deploy docs --project-name=management-dashboard --branch=main
```

Notes for the implementer: wrangler reads both env vars natively — no flags needed for
auth. `--branch=main` marks the upload as the production deployment. `npx --yes` avoids
an interactive install prompt on the runner.

- [ ] **Step 4: Run the full suite to verify everything passes**

Run: `python3 -m pytest scripts/ -q`
Expected: all pass, zero failures. The pre-existing guards in
`test_workflow_publish.py` must still pass — especially
`test_collector_writes_outside_the_repo` (the collector's `--out` still targets `/tmp`)
and `test_workflow_has_no_pages_publishing` (wrangler is not GitHub Pages).

- [ ] **Step 5: Commit (local only — do NOT push; see Global Constraints ordering)**

```bash
git add scripts/test_workflow_deploy.py .github/workflows/collect.yml
git commit -m "ci: deploy dashboard to Cloudflare Pages after nightly collect"
```

---

### Task 2: README — document the hosted dashboard

**Files:**
- Modify: `README.md` — the architecture line (~line 6) and a new section before `## Private 模式`

**Interfaces:**
- Consumes: URL and behaviour defined in Task 1 / spec (nothing programmatic).
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Update the architecture one-liner**

In the fenced block near the top of `README.md`, replace the trailing parenthetical

`dashboard(本機睇,經 private data repo 攞 metrics.json;認證 host 已取消)`

with

`dashboard(線上 https://management-dashboard-emj.pages.dev 經 Cloudflare Access 登入;或本機經 private data repo)`

- [ ] **Step 2: Add the hosted-viewing section**

Insert a new `##` section immediately before `## Private 模式`:

```markdown
## 線上睇(Cloudflare Pages + Access)

Dashboard 已經 host 喺 **https://management-dashboard-emj.pages.dev** — 開個 URL,輸入你嘅
email,收一封一次性驗證碼(One-time PIN)郵件,入碼就睇到。唔使密碼、唔使裝任何嘢。
只有名單內嘅 email 先入到;`/data/metrics.json` 同埋所有 preview URL 一樣受保護,
未登入直接開只會見到 Cloudflare 登入頁。

- **數據更新**:同 private data repo 同一條 nightly pipeline(`collect.yml` 最尾一步
  用 wrangler 直接 upload `docs/`,每日 05:00 HKT)。頁面數據以 header 嘅
  `generated_at` 為準。
- **加人 / 減人**:Cloudflare Zero Trust → Access → Applications → 個 dashboard app
  → 改 policy 嘅 email 名單,即時生效,唔使重新 deploy。
- **同 Phase 1 嘅關係**:Phase 1「淨用 GitHub、唔加第三方」嘅約束由
  `specs/2026-07-28-phase-2-cloudflare-pages-access-design.md` 正式取代 —
  metrics 而家會存放喺 Cloudflare(Access 後面,唔公開)。下面「Private 模式」
  嘅本地流程照用得,係冇網絡時嘅 fallback。
- **CI 紅咗、step 叫 `Deploy dashboard to Cloudflare Pages`**:多數係
  `CLOUDFLARE_API_TOKEN` 過期或者未設 — 去 repo Settings → Secrets and variables
  → Actions 換一個新 token(Cloudflare My Profile → API Tokens 開,權限只需要
  Account / Cloudflare Pages / Edit)。
```

- [ ] **Step 3: Run the suite**

Run: `python3 -m pytest scripts/ -q`
Expected: all pass.

- [ ] **Step 4: Commit (local only)**

```bash
git add README.md
git commit -m "docs: document the Cloudflare Pages + Access hosted dashboard"
```

---

### Task 3: Cloudflare one-time setup (HUMAN — guided, ~10 min)

No files. The session agent walks the user through these in order. UI labels drift —
the verification at each step is the ground truth, not the exact click path.

- [ ] **M1 — Pages project with a placeholder.** dash.cloudflare.com → Workers & Pages
  → Create → Pages → **Upload assets** (Direct Upload, NOT Git integration — the real
  content includes a gitignored file). Project name: exactly `management-dashboard`.
  Upload a single throwaway `index.html` containing just the word `placeholder`
  (create it locally; never upload real data here). Deploy.
  **Verify:** `https://management-dashboard-emj.pages.dev` shows "placeholder".
- [ ] **M2 — Zero Trust team.** one.dash.cloudflare.com → if prompted, pick any team
  name (free plan, 50 seats). **Verify:** Zero Trust dashboard opens.
- [ ] **M3 — Access application.** Zero Trust → Access → Applications → Add an
  application → **Self-hosted**. Name: `ManagementDashboard`. Add BOTH domains:
  `management-dashboard-emj.pages.dev` and `*.management-dashboard-emj.pages.dev`
  (production + preview URLs). (If instead enabled via Pages project → Settings →
  Access Policy toggle: it auto-creates the app for preview URLs — then EDIT it in
  Zero Trust to add the production hostname too.)
- [ ] **M4 — Policy.** In that application: one Allow policy, Include → Emails →
  `wingpoon1990@gmail.com`, `wing.poon@chinasofti.com`, `Shane.chan@chinasofti.com`.
  Login method: One-time PIN (default). Remove/avoid any broader rule
  (e.g. "everyone with account email domain").
- [ ] **M5 — Verify the gate BEFORE any real data exists.** In a private/incognito
  window open `https://management-dashboard-emj.pages.dev` → must show the Cloudflare
  Access login page, NOT "placeholder". Then log in with `wingpoon1990@gmail.com`
  (OTP email) → now shows "placeholder". A non-allowlisted email must be rejected.
  **Do not proceed to Task 4 until this passes.**
- [ ] **M6 — API token + GitHub secrets (user handles the value alone).**
  dash.cloudflare.com → My Profile → API Tokens → Create Token → **Create Custom
  Token** (the template list has no Pages entry). Permission: **Account → Cloudflare
  Pages → Edit**, Account Resources scoped to this account. Copy the token. Find the Account ID (Workers & Pages overview,
  right column). Then in GitHub: `wing-csi/ManagementDashboard` → Settings → Secrets
  and variables → Actions → New repository secret ×2: `CLOUDFLARE_API_TOKEN` (the
  token), `CLOUDFLARE_ACCOUNT_ID` (the account id). The agent never sees either value.

---

### Task 4: Push + end-to-end verification

**Files:** none (git push + checks only).

**Interfaces:**
- Consumes: Tasks 1–2 commits (local), Task 3 completed (Access verified, secrets set).

- [ ] **Step 1: Push (this also triggers the workflow — collect.yml runs on push to main touching `.github/workflows/**`)**

```bash
git push
```

- [ ] **Step 2: Watch the run to green**

```bash
gh run watch $(gh run list --workflow=collect.yml --limit 1 --json databaseId --jq '.[0].databaseId')
```

Expected: all steps green, including `Deploy dashboard to Cloudflare Pages`.
If the deploy step fails on missing secrets, Task 3 M6 was not completed — finish it
and re-run: `gh workflow run collect.yml`.

- [ ] **Step 3: Verify the spec's definition-of-done checklist**

```bash
curl -sI https://management-dashboard-emj.pages.dev/ | head -5
curl -sI https://management-dashboard-emj.pages.dev/data/metrics.json | head -5
```

Expected: both return a 302 redirect to `*.cloudflareaccess.com` (NOT 200).
Then in a browser, log in with an allowlisted email → dashboard renders real data,
`generated_at` in the header matches today's run, no console errors.
Non-allowlisted email → rejected. Tick the checklist in
`specs/2026-07-28-phase-2-cloudflare-pages-access-design.md` §Verification.

- [ ] **Step 4: Final suite + spec checkbox commit**

```bash
python3 -m pytest scripts/ -q
git add specs/2026-07-28-phase-2-cloudflare-pages-access-design.md
git commit -m "docs: tick Phase 2 verification checklist"
git push
```
