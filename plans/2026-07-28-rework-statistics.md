# Rework Statistics Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct six defects in how the dashboard calculates PR rework and acceptance, and add two new statistics — 返工周轉時間 and 平均返工輪數.

**Architecture:** The collector (`scripts/collect_github.py`) learns to see rejections it currently misses (dismissed ones), stops counting rejections it should not (self-reviews, raw event counts), and emits three new per-task fields. The frontend (`docs/js/*`) aggregates those fields into a corrected 打回率 with an honest denominator plus one new KPI card. Nothing about the collection→JSON→browser data flow changes shape; only fields are added.

**Tech Stack:** Python 3.14 (stdlib only, no dependencies), GitHub GraphQL v4, vanilla ES modules, pytest, pytest-playwright.

**Spec:** [specs/2026-07-28-rework-statistics-design.md](../specs/2026-07-28-rework-statistics-design.md)

## Global Constraints

- **No new dependencies.** `collect_github.py` is stdlib-only by design. Do not add any import that is not already in the file.
- **`from __future__ import annotations` is already present** at [collect_github.py:31](../scripts/collect_github.py). Modern annotations (`list[str]`, `str | None`) are safe everywhere in that file.
- **Never modify `scripts/fixtures/metrics-fixture.json` or `scripts/fixtures/rendered-baseline.json`.** Standing rule from [plans/2026-07-28-owner-contributor-filter.md:722-724](2026-07-28-owner-contributor-filter.md) — their entire value is proving the *default* render did not shift. Verified in spec §6.2 that this change does not require touching them.
- **Never swap `docs/data/metrics.json` on disk in a test.** That file holds the operator's real ~1.2 MB private data. Serve fixtures by intercepting the request with `page.route`, per [test_frontend_people.py:5-9](../scripts/test_frontend_people.py).
- **`docs/` is the published Cloudflare Pages root.** Plans and specs never go there.
- **Commit format:** `<type>: <description>` (feat, fix, refactor, docs, test, chore). No attribution footer — disabled globally.
- **Immutability:** build new lists/tuples, never mutate a passed-in argument.
- Run the full Python suite with `python -m pytest scripts/ -v`. Frontend modules self-skip when `pytest-playwright` is absent.

---

### Task 1: `rework_rounds()` — the round-counting primitive

A "round" is the unit the whole change hinges on. Today the collector counts `CHANGES_REQUESTED` *events*, so two reviewers rejecting the same push reads as 2. A round is instead a maximal run of rejections with **no push between them**.

This task builds it as a pure function with no I/O so it can be tested directly.

**Files:**
- Modify: `scripts/collect_github.py` (add function near `_lead_hours`, ~line 577)
- Test: `scripts/test_collect_github.py`

**Interfaces:**
- Consumes: nothing
- Produces: `rework_rounds(rejections: list[str], pushes: list[str]) -> int` — both arguments are lists of ISO-8601 UTC timestamp strings (e.g. `"2026-05-02T10:00:00Z"`), returns `0` for empty `rejections`. Task 3 calls this.

- [ ] **Step 1: Write the failing tests**

Add to `scripts/test_collect_github.py`. Put these directly after the existing `test_pr_rework_counts_multiple_changes_requested` (~line 335):

```python
# ------------------------------------------------------- rework rounds

def test_rework_rounds_no_rejections_is_zero():
    assert rework_rounds([], ["2026-05-01T09:00:00Z"]) == 0


def test_rework_rounds_two_reviewers_same_push_is_one_round():
    # Amy and Bob both reject the same code — one round trip for the author.
    assert rework_rounds(
        ["2026-05-02T10:00:00Z", "2026-05-02T11:00:00Z"],
        ["2026-05-01T09:00:00Z"],
    ) == 1


def test_rework_rounds_push_between_rejections_starts_a_new_round():
    assert rework_rounds(
        ["2026-05-02T10:00:00Z", "2026-05-04T10:00:00Z"],
        ["2026-05-01T09:00:00Z", "2026-05-03T09:00:00Z"],
    ) == 2


def test_rework_rounds_sorts_its_input():
    # GitHub does not promise ordering; the function must not trust it.
    assert rework_rounds(
        ["2026-05-04T10:00:00Z", "2026-05-02T10:00:00Z"],
        ["2026-05-03T09:00:00Z"],
    ) == 2


def test_rework_rounds_push_before_first_rejection_does_not_add_a_round():
    assert rework_rounds(
        ["2026-05-02T10:00:00Z"],
        ["2026-05-01T09:00:00Z", "2026-05-01T10:00:00Z"],
    ) == 1
```

Add `rework_rounds` to the import block at [test_collect_github.py:14-23](../scripts/test_collect_github.py), keeping the list alphabetical:

```python
from collect_github import (  # noqa: E402
    DEFAULT_CLASSIFY,
    CollectError,
    classify,
    collect_commits,
    collect_issues,
    collect_prs,
    load_config,
    normalize_level,
    rework_rounds,
)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest scripts/test_collect_github.py -k rework_rounds -v
```

Expected: collection error — `ImportError: cannot import name 'rework_rounds' from 'collect_github'`.

- [ ] **Step 3: Write the implementation**

Insert into `scripts/collect_github.py` immediately after `_lead_hours` (which ends at line 576) and before `_ci_state`:

```python
def rework_rounds(rejections: list[str], pushes: list[str]) -> int:
    """Count rework round-trips, not rejection events.

    A round is a maximal run of rejections with no push between them: two
    reviewers rejecting the same code is one round trip for the author, while
    a rejection arriving after a fresh push starts a new one.

    Both arguments are ISO-8601 UTC timestamps, which compare correctly as
    plain strings, so no parsing is needed.
    """
    if not rejections:
        return 0
    rejects = sorted(rejections)
    pushed = sorted(pushes)
    rounds = 1
    for prev, cur in zip(rejects, rejects[1:]):
        if any(prev < p <= cur for p in pushed):
            rounds += 1
    return rounds
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest scripts/test_collect_github.py -k rework_rounds -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/collect_github.py scripts/test_collect_github.py
git commit -m "feat: add rework_rounds to count round-trips not rejection events"
```

---

### Task 2: See every rejection, and only real reviews

Three signal-level corrections, all inside `extract_signals`:

- **Defect 3** — GitHub rewrites a dismissed review's `state` to `DISMISSED`, so it stops matching `CHANGES_REQUESTED` and vanishes. The timeline's `REVIEW_DISMISSED_EVENT` carries `previousReviewState` and is the only place it survives.
- **Defect 4** — a dedicated `states:[CHANGES_REQUESTED]` connection stops rejections competing with chatty `COMMENTED` reviews for the 50-node budget.
- **Defect 7** — GitHub permits an author to submit a `COMMENTED` review on their own PR. Today that counts as a human review, which both inflates the new denominator and silently suppresses the `merged-without-review` red line.

**Files:**
- Modify: `scripts/collect_github.py` — `PRS_QUERY` (lines 94-113), `PrSignals` (lines 361-374), `extract_signals` (lines 388-415)
- Test: `scripts/test_collect_github.py` — extend `pr_node` (lines 63-96), add tests

**Interfaces:**
- Consumes: nothing from Task 1
- Produces: `PrSignals.rejections: tuple[str, ...]` — sorted submit timestamps of every human rejection, live and dismissed. `PrSignals.changes_requested` becomes `len(rejections)`. `PrSignals.human_reviews` now excludes `PENDING` reviews and the PR author's own reviews. Task 3 reads `rejections`.

- [ ] **Step 1: Extend the `pr_node` test helper**

Replace `pr_node` at [test_collect_github.py:63-96](../scripts/test_collect_github.py) entirely:

```python
def pr_node(number=1, title="feat: y", body="", labels=(), author="wing",
            author_type="User", merged="2026-05-02T10:00:00Z", updated=None, add=50,
            commits=(), merged_by=("wing", "User"), auto_merge=False, reviews=(),
            threads=0, files=(), branch="feature/demo",
            created="2026-05-01T10:00:00Z", closed=None, ci=None, base="main",
            dismissed=(), pushes=()):
    """Build a fake PR node.

    reviews:   (state, login, __typename) or (state, login, __typename, submittedAt)
    dismissed: (previousReviewState, login, __typename, submittedAt) — reviews GitHub
               has rewritten to DISMISSED, which survive only on the timeline
    pushes:    committedDate per commit, positionally; commits past the end of this
               tuple fall back to a fixed early date
    """
    rows = [
        {"state": r[0],
         "author": {"login": r[1], "__typename": r[2]},
         "submittedAt": r[3] if len(r) > 3 else "2026-05-01T12:00:00Z"}
        for r in reviews
    ]
    return {
        "number": number,
        "headRefName": branch,
        "baseRefName": base,
        "title": title,
        "body": body,
        "mergedAt": merged,
        "createdAt": created,
        "closedAt": closed or merged or updated,
        "updatedAt": updated or merged,
        "additions": add,
        "deletions": 5,
        "url": f"https://github.com/wing/abci/pull/{number}",
        "author": {"login": author, "__typename": author_type},
        "mergedBy": {"login": merged_by[0], "__typename": merged_by[1]},
        "autoMergeRequest": {"enabledBy": {"login": "agent"}} if auto_merge else None,
        "reviews": {
            "nodes": [{"state": r["state"], "author": r["author"]} for r in rows],
        },
        "rejections": {"nodes": [
            {"author": r["author"], "submittedAt": r["submittedAt"]}
            for r in rows if r["state"] == "CHANGES_REQUESTED"
        ]},
        "timelineItems": {"nodes": [
            {"previousReviewState": st,
             "dismissedReview": {"submittedAt": at,
                                 "author": {"login": lg, "__typename": tp}}}
            for (st, lg, tp, at) in dismissed
        ]},
        "reviewThreads": {"totalCount": threads},
        "labels": {"nodes": [{"name": l} for l in labels]},
        "commits": {"nodes": [
            {"commit": {"message": m,
                        "committedDate": pushes[i] if i < len(pushes)
                        else "2026-05-01T09:00:00Z"}}
            for i, m in enumerate(commits)
        ]},
        "lastCommit": {"nodes": [{"commit": {"statusCheckRollup": {"state": ci} if ci else None}}]},
        "files": {"nodes": [
            {"path": f, "changeType": "MODIFIED"} if isinstance(f, str)
            else {"path": f[0], "changeType": f[1]} for f in files
        ]},
    }
```

- [ ] **Step 2: Write the failing tests**

Leave the existing `test_pr_rework_counts_multiple_changes_requested` at [test_collect_github.py:329-334](../scripts/test_collect_github.py) **alone for now** — Task 3 replaces it, because its `assert t.rework == 2` only becomes wrong once rounds are wired onto the `Task`. Add these new tests after it:

```python
def test_dismissed_rejection_is_still_counted():
    # GitHub rewrites the review's state to DISMISSED, so it survives only on
    # the timeline. Dismissing a rejection must not erase that it happened.
    t = infer_one(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,),
                  dismissed=(("CHANGES_REQUESTED", "bob", "User", "2026-05-02T10:00:00Z"),),
                  pushes=("2026-05-01T09:00:00Z",))
    assert t.rework == 1


def test_dismissed_approval_is_not_counted_as_rework():
    t = infer_one(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,),
                  dismissed=(("APPROVED", "bob", "User", "2026-05-02T10:00:00Z"),))
    assert t.rework == 0


def test_bot_rejection_is_not_counted():
    t = infer_one(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,),
                  reviews=(("CHANGES_REQUESTED", "sonar[bot]", "Bot",
                            "2026-05-02T10:00:00Z"),))
    assert t.rework == 0
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
python -m pytest scripts/test_collect_github.py -k "dismissed or bot_rejection" -v
```

Expected: `test_dismissed_rejection_is_still_counted` fails with `assert 0 == 1` — the dismissed rejection is invisible until the timeline is queried. The other two already pass; they are the guards proving the fix does not over-count.

- [ ] **Step 4: Update the GraphQL query**

In `scripts/collect_github.py`, replace the `reviews` line and the `commits` line inside `PRS_QUERY` (lines 104 and 107):

```graphql
        reviews(first:50){ nodes{ state author{ login __typename } } }
        rejections: reviews(first:50, states:[CHANGES_REQUESTED]){
          nodes{ author{ login __typename } submittedAt } }
        timelineItems(first:20, itemTypes:[REVIEW_DISMISSED_EVENT]){
          nodes{ ... on ReviewDismissedEvent {
            previousReviewState
            dismissedReview{ submittedAt author{ login __typename } } } } }
        reviewThreads(first:1){ totalCount }
        labels(first:20){ nodes{ name } }
        commits(first:50){ nodes{ commit{ message committedDate } } }
```

`dismissedReview.submittedAt` is deliberate — round detection needs when the rejection was *made*, not when it was waved away.

- [ ] **Step 5: Add `rejections` to `PrSignals`**

At [collect_github.py:374](../scripts/collect_github.py), after the `approvals` field:

```python
    approvals: int = 0  # human APPROVED reviews
    rejections: tuple[str, ...] = ()  # submit times of human rejections, live + dismissed
```

- [ ] **Step 6: Rewrite the review extraction**

In `extract_signals`, replace the `reviews = [...]` list comprehension (lines 394-397) with:

```python
    pr_author = (node.get("author") or {}).get("login") or ""
    reviews = [
        r for r in (node.get("reviews") or {}).get("nodes", [])
        if not _is_bot(r.get("author"), cfg)
        # PENDING = an unsubmitted draft review, not yet a review of anything.
        and r.get("state") != "PENDING"
        # Defect 7: GitHub blocks self-approve and self-request-changes but
        # permits a COMMENTED self-review. Counting it lets an author mark
        # their own PR "reviewed" and suppress merged-without-review.
        and not (pr_author and (r.get("author") or {}).get("login") == pr_author)
    ]
    rejections = _rejection_times(node, cfg)
```

Then change the two affected `PrSignals(...)` arguments (lines 403-404):

```python
        human_reviews=len(reviews),
        changes_requested=len(rejections),
```

and add to the same call, after `approvals=...`:

```python
        rejections=rejections,
```

- [ ] **Step 7: Add the rejection-gathering helper**

Insert directly above `extract_signals` (before line 388):

```python
def _rejection_times(node: dict, cfg: dict) -> tuple[str, ...]:
    """Submit times of every human CHANGES_REQUESTED review, live and dismissed.

    Dismissing a rejection rewrites its `state` to DISMISSED, so it disappears
    from `reviews` — REVIEW_DISMISSED_EVENT.previousReviewState is the only
    place it survives. Because a dismissed review is no longer CHANGES_REQUESTED
    in `reviews`, the two sources never overlap and nothing is double-counted.

    Self-rejection needs no filter: GitHub does not allow an author to request
    changes on their own PR.
    """
    times = [
        r["submittedAt"]
        for r in (node.get("rejections") or {}).get("nodes", [])
        if r.get("submittedAt") and not _is_bot(r.get("author"), cfg)
    ]
    for ev in (node.get("timelineItems") or {}).get("nodes", []):
        if ev.get("previousReviewState") != "CHANGES_REQUESTED":
            continue
        review = ev.get("dismissedReview") or {}
        if review.get("submittedAt") and not _is_bot(review.get("author"), cfg):
            times.append(review["submittedAt"])
    return tuple(sorted(times))
```

- [ ] **Step 8: Run the whole Python suite**

```bash
python -m pytest scripts/test_collect_github.py -v
```

Expected: **all pass**, including the pre-existing `test_pr_rework_counts_multiple_changes_requested` — after this task `changes_requested` is `len(rejections)`, which is still 2 for two reviewers. Task 3 is what makes that assertion wrong, and Task 3 replaces it.

If a pre-existing inference test broke, the cause is almost certainly `changes_requested` now including dismissed rejections in `infer_level` / `verify_claim`. That is the intended improvement — a dismissed rejection is still a human gate that happened. Update the test's expectation, do not revert the behaviour.

- [ ] **Step 9: Commit**

```bash
git add scripts/collect_github.py scripts/test_collect_github.py
git commit -m "fix: count dismissed rejections and stop counting self-reviews

- REVIEW_DISMISSED_EVENT recovers rejections GitHub rewrote to DISMISSED
- dedicated states:[CHANGES_REQUESTED] connection ends contention with
  COMMENTED reviews for the 50-node budget
- a PR author's own COMMENTED review no longer counts as a human review,
  which also closes a merged-without-review bypass"
```

---

### Task 3: Emit `reviewed`, round-based `rework`, and `rework_hours`

**Files:**
- Modify: `scripts/collect_github.py` — `Task` (lines 214-232), `collect_prs` (lines 623-643)
- Test: `scripts/test_collect_github.py`

**Interfaces:**
- Consumes: `rework_rounds()` (Task 1), `PrSignals.rejections` (Task 2)
- Produces: three JSON fields on every PR task, serialized automatically by the existing `asdict` at [collect_github.py:41](../scripts/collect_github.py) — `reviewed: bool`, `rework: int` (rounds), `rework_hours: float | None`. Tasks 5 and 6 read these.

- [ ] **Step 1: Write the failing tests**

First **replace** the existing `test_pr_rework_counts_multiple_changes_requested` at [test_collect_github.py:329-334](../scripts/test_collect_github.py). Its `assert t.rework == 2` **is defect 5** — two reviewers on one push is one round trip, not two:

```python
def test_two_reviewers_on_the_same_push_is_one_round():
    t = infer_one(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,),
                  reviews=(("CHANGES_REQUESTED", "bob", "User", "2026-05-02T10:00:00Z"),
                           ("CHANGES_REQUESTED", "amy", "User", "2026-05-02T11:00:00Z"),
                           ("APPROVED", "bob", "User")),
                  pushes=("2026-05-01T09:00:00Z",))
    assert t.rework == 1


def test_rejection_after_a_push_is_a_second_round():
    t = infer_one(labels=("ai-level/L3",),
                  commits=(CLAUDE_FOOTER, CLAUDE_FOOTER),
                  reviews=(("CHANGES_REQUESTED", "bob", "User", "2026-05-02T10:00:00Z"),
                           ("CHANGES_REQUESTED", "bob", "User", "2026-05-04T10:00:00Z")),
                  pushes=("2026-05-01T09:00:00Z", "2026-05-03T09:00:00Z"))
    assert t.rework == 2
```

Then append the rest:

```python
def test_reviewed_is_false_without_any_human_review():
    t = infer_one(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,))
    assert t.reviewed is False


def test_reviewed_is_true_with_an_outside_review():
    t = infer_one(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,),
                  reviews=(("APPROVED", "bob", "User"),))
    assert t.reviewed is True


def test_authors_own_comment_does_not_make_a_pr_reviewed():
    # Defect 7: this is the bypass. "wing" opens the PR and comments on it.
    t = infer_one(labels=("ai-level/L3",), author="wing", commits=(CLAUDE_FOOTER,),
                  reviews=(("COMMENTED", "wing", "User"),))
    assert t.reviewed is False
    assert "merged-without-review" in t.violations


def test_rework_hours_measured_from_the_first_rejection():
    # First rejection 2026-05-02T10:00Z, merged 2026-05-04T10:00Z = 48h.
    t = infer_one(labels=("ai-level/L3",),
                  commits=(CLAUDE_FOOTER, CLAUDE_FOOTER),
                  merged="2026-05-04T10:00:00Z",
                  reviews=(("CHANGES_REQUESTED", "bob", "User", "2026-05-02T10:00:00Z"),
                           ("CHANGES_REQUESTED", "amy", "User", "2026-05-03T10:00:00Z")),
                  pushes=("2026-05-01T09:00:00Z", "2026-05-02T20:00:00Z"))
    assert t.rework_hours == 48.0


def test_no_rejection_means_no_rework_hours():
    t = infer_one(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,),
                  reviews=(("APPROVED", "bob", "User"),))
    assert t.rework == 0 and t.rework_hours is None
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest scripts/test_collect_github.py -k "reviewed or rework_hours or no_rejection or round" -v
```

Expected: the `reviewed` / `rework_hours` tests fail with `AttributeError: 'Task' object has no attribute 'reviewed'`, and `test_two_reviewers_on_the_same_push_is_one_round` fails with `assert 2 == 1` because `rework` is still the raw event count.

- [ ] **Step 3: Add the `Task` fields**

At [collect_github.py:229](../scripts/collect_github.py), replace the `rework` line with these three:

```python
    reviewed: bool = False  # ≥1 human review by someone other than the PR author
    rework: int = 0  # rework rounds — rejections separated by a push (被打回輪數)
    rework_hours: float | None = None  # first rejection → mergedAt (返工周轉時間)
```

Keep them adjacent to the existing `violations` / `lead_hours` / `ci` fields; all have defaults, so ordering within the defaulted block is free.

- [ ] **Step 4: Wire them up in `collect_prs`**

Inside the `for node in conn["nodes"]:` loop, after `sig = extract_signals(node, cfg)` (line 612), add:

```python
            pushes = [
                c["commit"]["committedDate"]
                for c in (node.get("commits") or {}).get("nodes", [])
                if c.get("commit", {}).get("committedDate")
            ]
```

Then in the `Task(...)` construction, replace the `rework=sig.changes_requested,` line (line 638) with:

```python
                    reviewed=sig.human_reviews > 0,
                    rework=rework_rounds(list(sig.rejections), pushes),
                    rework_hours=(
                        _lead_hours(sig.rejections[0], node["mergedAt"])
                        if sig.rejections else None
                    ),
```

- [ ] **Step 5: Run the whole Python suite**

```bash
python -m pytest scripts/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/collect_github.py scripts/test_collect_github.py
git commit -m "feat: emit reviewed, rework rounds, and rework_hours per PR"
```

---

### Task 4: Apply `exclude_authors` to closed PRs too

**Defect 8.** In `collect_prs` the `exclude_authors` check sits *below* the non-merged early-`continue`, so an excluded author's **merged** PRs are dropped while their **closed** PRs still land in `closed_unmerged`. Default `exclude_authors` is `["dependabot[bot]", "renovate[bot]", "github-actions[bot]"]` ([config.toml:149](../config.toml)) and dependabot PRs are closed and superseded constantly — every one deflates 接受率. [README.md:402](../README.md) already promises 「完全唔計呢啲 author」, so this aligns code with its documented contract.

Independent of Tasks 1-3; can be reviewed on its own.

**Files:**
- Modify: `scripts/collect_github.py` — `collect_prs` (lines 595-605)
- Test: `scripts/test_collect_github.py`

**Interfaces:**
- Consumes: nothing
- Produces: nothing new — `collect_prs` keeps returning `tuple[list[Task], list[str]]`

- [ ] **Step 1: Write the failing test**

```python
def test_excluded_author_closed_pr_stays_out_of_closed_unmerged():
    # A closed dependabot PR must not deflate 接受率 — README promises
    # exclude_authors means 「完全唔計呢啲 author」, merged or not.
    client = FakeClient([prs_page([
        pr_node(number=7, author="dependabot[bot]", author_type="Bot",
                merged=None, closed="2026-05-02T10:00:00Z",
                updated="2026-05-02T10:00:00Z"),
    ])])
    tasks, closed_unmerged = collect_prs(client, "wing/abci", SINCE, CFG)
    assert tasks == []
    assert closed_unmerged == []


def test_included_author_closed_pr_is_still_counted():
    client = FakeClient([prs_page([
        pr_node(number=8, author="wing", merged=None,
                closed="2026-05-02T10:00:00Z", updated="2026-05-02T10:00:00Z"),
    ])])
    tasks, closed_unmerged = collect_prs(client, "wing/abci", SINCE, CFG)
    assert tasks == []
    assert closed_unmerged == ["2026-05-02"]
```

- [ ] **Step 2: Run the tests to verify the first fails**

```bash
python -m pytest scripts/test_collect_github.py -k "closed_unmerged or closed_pr" -v
```

Expected: `test_excluded_author_closed_pr_stays_out_of_closed_unmerged` fails with `assert ['2026-05-02'] == []`. The second test passes already — it is the regression guard proving the fix does not over-filter.

- [ ] **Step 3: Move the author check above the merge check**

In `collect_prs`, replace lines 595-605 (the top of the `for node in conn["nodes"]:` body) with:

```python
        for node in conn["nodes"]:
            # exclude_authors means 「完全唔計呢啲 author」 (README) — that has to
            # apply before the merged/closed split, or an excluded bot's closed
            # PRs still land in closed_unmerged and deflate 接受率.
            author = (node.get("author") or {}).get("login") or ""
            if author in cfg["exclude_authors"]:
                continue
            if not node["mergedAt"]:
                closed_at = node.get("closedAt") or ""
                if closed_at >= since_iso:
                    closed_unmerged.append(closed_at[:10])
                continue
            if node["mergedAt"] < since_iso:
                continue
            labels = tuple(l["name"] for l in node["labels"]["nodes"])
```

The old `author = ...` / `if author in cfg["exclude_authors"]` pair that sat below is now gone — verify it is not duplicated.

- [ ] **Step 4: Run the whole Python suite**

```bash
python -m pytest scripts/ -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/collect_github.py scripts/test_collect_github.py
git commit -m "fix: exclude_authors now applies to closed PRs, not just merged"
```

---

### Task 5: Aggregate the new fields

**Files:**
- Modify: `docs/js/aggregate.js` (lines 32-52)

**Interfaces:**
- Consumes: `reviewed`, `rework`, `rework_hours` on PR tasks (Task 3)
- Produces: on the stats object returned by `statsFromTasks` — `reviewedPRs: number`, `reworkPRs: number`, `reworkRounds: number[]`, `reworkTurnarounds: number[]`. Task 6 renders these.

- [ ] **Step 1: Add the counters to the accumulator**

In `statsFromTasks`, replace line 35:

```js
    fixTasks: 0, prTotal: 0, reviewedPRs: 0, reworkPRs: 0,
    reworkRounds: [], reworkTurnarounds: [], fixByLevel: {},
```

- [ ] **Step 2: Populate them in the PR branch**

Replace lines 47-52 (`if (t.kind === 'pr') { ... }`):

```js
    if (t.kind === 'pr') {
      s.prTotal++;
      // 打回率 分母係「有人 review 過」嘅 PR — 冇人 review 過嘅 PR 根本冇得被打回,
      // 擺入分母只會令個率虛低。
      if (t.reviewed) s.reviewedPRs++;
      if ((t.rework || 0) > 0) {
        s.reworkPRs++;
        s.reworkRounds.push(t.rework);
        if (t.rework_hours != null) s.reworkTurnarounds.push(t.rework_hours);
      }
      if (t.ci) { s.ciTotal++; if (t.ci === 'pass') s.ciPass++; }
      if (t.lead_hours != null) { s.leads.push(t.lead_hours); if (isFix) s.fixLeads.push(t.lead_hours); }
    }
```

- [ ] **Step 3: Verify nothing regressed**

```bash
python -m pytest scripts/test_frontend_snapshot.py -v
```

Expected: pass unchanged. The `.qgrid` block is not in `SECTION_IDS` and `metrics-fixture.json` has both tasks at `"rework": 0`, so this is confirming the baseline genuinely does not move. If it *does* fail, stop — that means a snapshotted section reads these fields and the spec's §6.2 analysis was wrong.

- [ ] **Step 4: Commit**

```bash
git add docs/js/aggregate.js
git commit -m "feat: aggregate reviewedPRs, rework rounds, and rework turnarounds"
```

---

### Task 6: Render the corrected 打回率 and the new 返工周轉時間 card

Three rendering changes plus their browser test:

- **打回率** switches denominator to `reviewedPRs` and gains median rounds in its sub-text (defects 1, 5).
- **返工周轉時間** is a new card (fifth in the grid).
- **接受率** renders `–` under a person filter (defect 6) — it divides person-scoped `prTotal` by repo-wide `closedUnmerged`, exactly what the owner-filter work already fixed for 變更失敗率 at [render-kpi.js:188](../docs/js/render-kpi.js).

**Files:**
- Create: `scripts/fixtures/metrics-fixture-rework.json`
- Create: `scripts/test_frontend_rework.py`
- Modify: `docs/js/render-kpi.js` (`renderQuality`, lines 238-252), `docs/js/render-table.js:138`, `docs/index.html` (lines 117-146), `docs/css/dashboard.css:302`

**Interfaces:**
- Consumes: `reviewedPRs`, `reworkPRs`, `reworkRounds`, `reworkTurnarounds` (Task 5); `median` and `fmtHours` from `./aggregate.js`; `pct` from `./data.js` — note `pct(num, den)` returns `null` when `den <= 0` ([data.js:6](../docs/js/data.js))
- Produces: DOM ids `qTurn`, `qTurnSub`; keeps `qRework`, `qReworkSub`, `qAccept`, `qAcceptSub`

- [ ] **Step 1: Create the fixture**

`scripts/fixtures/metrics-fixture-rework.json` — four PRs covering every branch of the new logic:

```json
{
 "schema_version": 2,
 "generated_at": "2026-07-28T05:00:00+00:00",
 "window_days": 180,
 "mode": "auto",
 "repos": ["acme/alpha"],
 "people": {"Wing": ["wing-csi"]},
 "tasks": [
  {"date": "2026-07-20", "repo": "acme/alpha", "author": "wing-csi", "id": "1", "kind": "pr", "branch": "main", "title": "feat: reviewed and rejected twice", "level": "L3", "method": "label", "check": null, "additions": 40, "deletions": 2, "url": "https://example.test/1", "reviewed": true, "rework": 2, "rework_hours": 48, "violations": [], "lead_hours": 60, "ci": "pass"},
  {"date": "2026-07-19", "repo": "acme/alpha", "author": "wing-csi", "id": "2", "kind": "pr", "branch": "main", "title": "feat: reviewed and rejected once", "level": "L3", "method": "label", "check": null, "additions": 30, "deletions": 1, "url": "https://example.test/2", "reviewed": true, "rework": 1, "rework_hours": 12, "violations": [], "lead_hours": 20, "ci": "pass"},
  {"date": "2026-07-18", "repo": "acme/alpha", "author": "wing-csi", "id": "3", "kind": "pr", "branch": "main", "title": "feat: reviewed and clean", "level": "L3", "method": "label", "check": null, "additions": 20, "deletions": 1, "url": "https://example.test/3", "reviewed": true, "rework": 0, "rework_hours": null, "violations": [], "lead_hours": 5, "ci": "pass"},
  {"date": "2026-07-17", "repo": "acme/alpha", "author": "Tony", "id": "4", "kind": "pr", "branch": "main", "title": "feat: auto-merged never reviewed", "level": "L5", "method": "label", "check": null, "additions": 10, "deletions": 0, "url": "https://example.test/4", "reviewed": false, "rework": 0, "rework_hours": null, "violations": [], "lead_hours": 1, "ci": "pass"}
 ],
 "repo_meta": {
  "acme/alpha": {"owner": "Wing", "disk_kb": 1024, "languages": {"items": [{"name": "Python", "bytes": 5000}]}, "deployments": [], "releases": [], "tags": [], "closed_unmerged": ["2026-07-16"], "issues": null}
 },
 "errors": []
}
```

Expected readings: 3 reviewed PRs, 2 of them rejected → 打回率 **66.7%**; rounds `[2, 1]` → median **1.5**; turnarounds `[48, 12]` → median **30.0** hours. The un-reviewed PR #4 is the one today's broken formula would have counted, which is what makes 2/3 differ from 2/4.

- [ ] **Step 2: Write the failing browser test**

Create `scripts/test_frontend_rework.py`:

```python
"""Behaviour tests for the corrected rework statistics.

The fixture is served by intercepting the metrics.json request, NOT by
swapping docs/data/metrics.json on disk — that file holds the operator's real
private data locally, and an interrupted swap-pattern run leaves a small test
fixture where it used to be. Same reasoning as test_frontend_people.py.

metrics-fixture.json and rendered-baseline.json are deliberately untouched:
their value is proving the *default* render did not shift.

Run:  python -m pytest scripts/test_frontend_rework.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pytest_playwright",
                    reason="rework statistics tests need pytest-playwright")

FIXTURE = Path(__file__).parent / "fixtures" / "metrics-fixture-rework.json"


@pytest.fixture()
def rework_page(page):
    """A page that receives the rework fixture in place of metrics.json."""
    body = FIXTURE.read_text(encoding="utf-8")
    page.route(
        "**/data/metrics.json",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body=body),
    )
    return page


def open_dashboard(rework_page, server, query: str = ""):
    rework_page.goto(f"{server}/{query}", wait_until="networkidle")
    rework_page.wait_for_selector("#taskRows tr")
    return rework_page


def test_rework_rate_denominator_excludes_unreviewed_prs(rework_page, server):
    page = open_dashboard(rework_page, server)
    # 2 rejected of 3 reviewed = 66.7%, NOT 2 of 4 merged = 50%.
    assert "66.7" in page.text_content("#qRework")


def test_rework_subtext_reports_reviewed_count_and_median_rounds(rework_page, server):
    page = open_dashboard(rework_page, server)
    sub = page.text_content("#qReworkSub")
    assert "2 / 3" in sub
    assert "1.5" in sub


def test_turnaround_card_shows_median_hours(rework_page, server):
    page = open_dashboard(rework_page, server)
    # median of [48, 12] = 30 hours; fmtHours renders <48h as hours.
    assert "30.0" in page.text_content("#qTurn")


def test_accept_rate_blanks_out_under_a_person_filter(rework_page, server):
    page = open_dashboard(rework_page, server, "?owner=Wing")
    # Person-scoped merges ÷ repo-wide closed PRs is not a rate.
    assert page.text_content("#qAccept").strip() == "–"


def test_accept_rate_still_renders_for_everyone(rework_page, server):
    page = open_dashboard(rework_page, server)
    assert page.text_content("#qAccept").strip() != "–"
```

- [ ] **Step 3: Run it to verify it fails**

```bash
python -m pytest scripts/test_frontend_rework.py -v
```

Expected: failures — `#qTurn` does not exist yet, and `#qRework` still reads `50.0`.

If every test *skips*, `pytest-playwright` is missing. Install it and the browser:

```bash
pip install pytest-playwright && python -m playwright install chromium
```

- [ ] **Step 4: Add the new KPI card to the markup**

In `docs/index.html`, insert a fifth `.kpi` block into `.qgrid` immediately after the `qRework` block (which ends at line 135):

```html
      <div class="kpi">
        <div class="label">返工周轉時間</div>
        <div class="value" id="qTurn">–</div>
        <div class="sub" id="qTurnSub">–</div>
      </div>
```

Also update the section's `card-note` at line 120 so it describes what is now measured:

```html
      <span class="card-note">fix / hotfix / revert 前綴 · PR 打回輪數(以 push 分隔)</span>
```

- [ ] **Step 5: Widen the grid**

In `docs/css/dashboard.css` line 302, change:

```css
.qgrid { grid-template-columns: repeat(5, 1fr); }
```

Leave line 297 (the narrow-container default) and line 332 (the mobile `repeat(2, 1fr)` override) alone — the mobile rule already handles the wrap.

- [ ] **Step 6: Rewrite `renderQuality`**

In `docs/js/render-kpi.js`, replace lines 242-252 (from `const rp = ...` through the `qAcceptSub` assignment):

```js
  // 打回率 分母係「有人 review 過」嘅 PR — 冇人 review 過嘅 PR 根本冇得被打回,
  // 擺入分母等同當佢「通過咗 review」。
  const rp = pct(cur.reworkPRs, cur.reviewedPRs);
  $('qRework').innerHTML = rp == null ? '–' : `${rp}<span class="unit">%</span>`;
  if (cur.reviewedPRs) {
    const mr = median(cur.reworkRounds);
    $('qReworkSub').textContent =
      `${cur.reworkPRs} / ${cur.reviewedPRs} 個有 review 嘅 PR 被打回 · 中位 ${mr} 輪`;
  } else {
    $('qReworkSub').textContent = cur.prTotal
      ? '此範圍內無經 review 嘅 PR'
      : '此範圍內無 PR';
  }

  $('qTurn').innerHTML = fmtHours(median(cur.reworkTurnarounds));
  $('qTurnSub').textContent = cur.reworkTurnarounds.length
    ? `由第一次打回到 merge · ${cur.reworkTurnarounds.length} 個 PR`
    : '此範圍內無被打回嘅 PR';

  const meta = metaInWindow();
  // 一個人嘅 merged PR ÷ 全 repo 嘅 closed PR 唔係一個比率 — closed_unmerged
  // 係 repo 層面 metadata,冇 person 維度(同 變更失敗率 一樣嘅處理)。
  const ap = state.person === 'all'
    ? pct(cur.prTotal, cur.prTotal + meta.closedUnmerged) : null;
  $('qAccept').innerHTML = ap == null ? '–' : `${ap}<span class="unit">%</span>`;
  $('qAcceptSub').textContent = state.person !== 'all'
    ? '需要全員範圍(closed PR 冇 person 維度)'
    : ((cur.prTotal + meta.closedUnmerged)
      ? `${cur.prTotal} merged / ${meta.closedUnmerged} 個 close 咗冇 merge`
      : '此範圍內無 PR');
```

Confirm the imports at the top of `render-kpi.js` already provide `median`, `fmtHours`, `pct`, and `state`. `median` and `fmtHours` come from `./aggregate.js` ([aggregate.js:27-28](../docs/js/aggregate.js)); `pct` and `state` from `./data.js`. Add any that are missing to the existing import statements.

- [ ] **Step 7: Reword the table badge**

In `docs/js/render-table.js:138`, the badge tooltip now describes rounds:

```js
${(r.rework || 0) > 0 ? `<span class="rework" title="被打回 ${r.rework} 輪">↩${r.rework}</span>` : ''}
```

- [ ] **Step 8: Run the browser tests**

```bash
python -m pytest scripts/test_frontend_rework.py scripts/test_frontend_snapshot.py scripts/test_frontend_people.py -v
```

Expected: all pass. The snapshot test passing confirms the baseline was genuinely unaffected.

- [ ] **Step 9: Commit**

```bash
git add docs/js/render-kpi.js docs/js/render-table.js docs/index.html docs/css/dashboard.css scripts/fixtures/metrics-fixture-rework.json scripts/test_frontend_rework.py
git commit -m "feat: correct PR 打回率 denominator and add 返工周轉時間 card

- 打回率 divides by reviewed PRs, not all merged PRs
- sub-text reports median rework rounds
- 接受率 blanks out under a person filter, matching 變更失敗率
- the badge now reads as rounds"
```

---

### Task 7: Documentation and demo data

The README states these definitions in four places; all must move together or the dashboard documents a formula it no longer uses.

**Files:**
- Modify: `README.md` (~lines 89-93, ~154, ~255-263, ~302-307)
- Modify: `docs/data/demo-data.js` via a one-off script

**Interfaces:**
- Consumes: the final formulas from Tasks 3, 5, 6
- Produces: nothing code-facing

- [ ] **Step 1: Update the 品質指標 table (~lines 89-93)**

Replace the 打回率 row and add the two new metrics:

```markdown
| PR 打回率 | 收過 ≥1 次 human `CHANGES_REQUESTED`(包括已 dismiss)嘅 PR ÷ **有人 review 過**嘅 PR × 100 | 字面意義嘅「被打回重做」 | 分母排除咗冇人 review 過嘅 PR — 冇人睇過嘅 PR 根本冇得被打回,計入分母只會令個率虛低。作者 review 自己個 PR 唔算 |
| 平均返工輪數 | 被打回 PR 嘅打回**輪數**中位數 | 一個 PR 被踢返嚟幾多轉 | 一輪 = 中間冇新 push 嘅一批打回;兩個 reviewer 打回同一個 push 算一輪 |
| 返工周轉時間 | 第一次打回 → merge 嘅中位時數 | 返工要幾耐先搞掂 | 量度成段返工期,唔係最後一輪 |
```

- [ ] **Step 2: Update the badge legend (~line 154)**

```markdown
| `↩N` | 呢個 PR 被打回(CHANGES_REQUESTED)N **輪** |
```

- [ ] **Step 3: Update the 品質 × 自動化 section (~lines 255-263)**

Replace the 打回率 row in that table:

```markdown
| PR 打回率 | 收過 `CHANGES_REQUESTED` 嘅 PR ÷ **有人 review 過**嘅 PR | 字面意義嘅「被打回重做」,直接嚟自 GitHub review 記錄 |
```

Then append to the caveat paragraph at line 263:

```markdown
分母用「有人 review 過嘅 PR」而唔係全部 merged PR:一個冇人 review 過就 merge 咗嘅 PR
(auto-merge、或者中咗 `merged-without-review` 紅線)根本冇機會被打回,擺入分母等同
當佢「通過咗 review」。作者 comment 自己個 PR 唔算 review。已經被 dismiss 嘅打回一樣照計 —
GitHub 會將佢個 state 改成 `DISMISSED`,但打回呢件事發生過。
```

- [ ] **Step 4: Update the DORA-adjacent table (~lines 302-307)**

```markdown
| PR 接受率 | merged ÷ (merged + closed 未 merge) | 直接(揀咗人之後顯示 `–`,closed PR 冇 person 維度)|
| 返工周轉時間 | 第一次打回 → merge 中位數 | 直接 |
```

- [ ] **Step 5: Add the fields to demo data**

`docs/data/demo-data.js` is a hand-extracted 80 KB single-line blob with no generator, so transform it with a script rather than editing by hand. Demo values are synthetic and that is legitimate — demo mode is opt-in behind `?demo=1` ([data.js:44-51](../docs/js/data.js)).

Write this to the scratchpad (not the repo) and run it from the repo root:

```python
"""One-off: add reviewed / rework_hours to the demo blob."""
import json
from pathlib import Path

p = Path("docs/data/demo-data.js")
src = p.read_text(encoding="utf-8")
prefix = "export const DEMO_DATA = "
assert src.startswith(prefix), "unexpected demo-data.js shape — inspect before writing"
data = json.loads(src[len(prefix):].rstrip().rstrip(";"))

for t in data["tasks"]:
    if t.get("kind") != "pr":
        continue
    rework = t.get("rework") or 0
    # Synthetic but self-consistent: a rejected PR was necessarily reviewed,
    # and its rework period is a fraction of its total lead time.
    t["reviewed"] = True
    t["rework_hours"] = round((t.get("lead_hours") or 0) * 0.6, 1) if rework else None

p.write_text(prefix + json.dumps(data, separators=(",", ":")) + ";\n", encoding="utf-8")
print(f"updated {sum(1 for t in data['tasks'] if t.get('kind') == 'pr')} PR tasks")
```

If the `assert` trips, the blob's prefix differs — inspect the first 80 characters and adjust rather than forcing the write.

- [ ] **Step 6: Verify the demo page still renders**

```bash
python -m pytest scripts/ -v
```

Then check the demo by eye — serve `docs/`, open `http://127.0.0.1:8765/?demo=1`, and confirm 打回率 shows a percentage and 返工周轉時間 shows hours rather than `–`:

```bash
python -m http.server 8765 -d docs
```

- [ ] **Step 7: Commit**

```bash
git add README.md docs/data/demo-data.js
git commit -m "docs: document the corrected rework formulas and refresh demo data"
```

---

## Self-Review

**Spec coverage** — every spec section maps to a task:

| Spec | Task |
|---|---|
| §3.1 query changes | 2 (step 4) |
| §3.2 `PrSignals`, self-review + PENDING exclusion | 2 (steps 5-7) |
| §3.3 `rework_rounds()` | 1 |
| §3.4 `Task` fields | 3 |
| §3.5 defect 8 ordering | 4 |
| §4 aggregation | 5 |
| §5.1 打回率, 返工周轉時間, 接受率 guard | 6 (step 6) |
| §5.2 markup + CSS | 6 (steps 4-5) |
| §5.3 badge tooltip | 6 (step 7) |
| §6.1 collector tests | 1, 2, 3, 4 |
| §6.2 baseline untouched | 5 (step 3), 6 (step 8) |
| §6.3 new fixture + route interception + demo blob | 6 (steps 1-2), 7 (step 5) |
| §6.4 README, four sites | 7 (steps 1-4) |

**Type consistency** — `rework_rounds(list[str], list[str]) -> int` is defined in Task 1 and called in Task 3 with `list(sig.rejections)`, converting the tuple. `PrSignals.rejections` is a tuple throughout. `reviewed` / `rework` / `rework_hours` keep identical names from Task 3 (Python) through Task 5 (JS reads) to Task 6 (render) and Task 7 (demo blob). DOM ids `qTurn` / `qTurnSub` are created in Task 6 step 4, used in step 6, and asserted in the test from step 2.

**Every task ends green.** The round assertions live in Task 3, not Task 2, precisely so no task finishes with a failing suite: after Task 2 `changes_requested` is `len(rejections)`, which still equals 2 for two reviewers, so the pre-existing `test_pr_rework_counts_multiple_changes_requested` keeps passing until Task 3 replaces it with the round-based version.
