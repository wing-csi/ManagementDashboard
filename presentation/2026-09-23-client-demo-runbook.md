# Client demo runbook — Wed 2026-09-23

Audience: client / external. Story: **the method and the workflow**, not our numbers.
**Delivery language: English.** The dashboard is demoed in English via `?lang=en`; the spoken
lines below are written to be said as-is.

---

## 1. Decision: present in demo mode, in English (`?demo=1&lang=en`)

**Recommendation: do the whole demo on `?demo=1&lang=en`, not on live data.**

Three independent reasons:

1. **Confidentiality.** The live dashboard tracks 14 repos belonging to several different
   clients. Repo names, contributor names, issue titles, defect registers and per-project
   delivery status are all on screen. Showing that to an external party discloses other
   clients' project data.
2. **It matches your story.** You are presenting the method, not our current numbers. Demo data
   is complete, stable, and nothing on screen invites a question about our own delivery.
3. **It is the only way the screen is fully English.** The demo dataset is ASCII throughout.
   Live `metrics.json` carries real commit titles written in Chinese — those are the artefact
   itself and are not translatable. On live data, the Tasks tab will show Chinese titles.

How to enter demo mode: add `?demo=1` to the URL. An orange badge
**"Demo data · explicitly requested (?demo=1)"** appears in the filter row, so the client can
see it is sample data — say so once, up front, and it never becomes an issue.

How to enter English: add `&lang=en`, or click the **EN** toggle at the right end of the filter
row. The language choice is remembered in the browser, and the URL is the authoritative
source — so a link you send is deterministic regardless of what the recipient has stored.

- Live (after Access login): `https://management-dashboard-emj.pages.dev/?demo=1&lang=en`
- Local fallback: `python -m http.server -d docs 8000` → `http://localhost:8000/?demo=1&lang=en`

### Two things on screen you should own before they ask

On the Overview tab, demo data shows **Delivery status "Unknown"** and **Data health "Stale"**.
Do not skip past these — they are the best trust moment in the whole demo:

> "I want you to see this deliberately. The demo dataset is a fixed snapshot, so the system
> immediately tells you it is stale. That is a designed safety net — once the data is more than
> 48 hours old, it would rather write 'Unknown' than show you a green light. A dashboard that
> only ever reports good news is one nobody can safely make a decision with."

---

## 2. Pre-flight checklist

**Tuesday night**

- [ ] Log in to `https://management-dashboard-emj.pages.dev` yourself (Cloudflare Access →
      email OTP to `Wing.poon@chinasofti.com`). Confirm the page renders after login. This is
      the one step nobody can do for you.
- [ ] Then open `…/?demo=1&lang=en` and click through all five tabs once. **Confirm every tab
      is fully English** — this is the check that matters most, because a missed string only
      shows up on the projector.
- [ ] Hard refresh (Ctrl+Shift+R). New JavaScript modules ship behind cache-busting tokens; a
      stale cache is the single most likely way English silently fails to load.
- [ ] Confirm the Access session will still be alive on Wednesday; if in doubt, log in again on
      the morning.
- [ ] Have the local fallback ready in a second tab (see command above), in case the venue
      network or the OTP email is slow.

**Wednesday, 15 minutes before**

- [ ] Browser zoom 100%, window maximised; the masthead and filters are sticky, so scrolling
      never loses the controls.
- [ ] Open on `?demo=1&lang=en#overview`. Have `#quality`, `#projects`, `#product`, `#tasks`
      ready — each tab has its own URL hash, so you can jump directly.
- [ ] Close unrelated tabs — an Access-protected internal dashboard in the tab strip is the
      kind of thing clients read.
- [ ] Hard refresh (Ctrl+Shift+R) once more, so no stale JS is cached.

---

## 3. Run of show (~22 min + Q&A)

Short on time? Keep stops 1, 2, 3, 6 and 8 — that is the 10-minute version.

### Stop 1 — The problem (2 min, no screen)

> "Every company now says they are using AI to write code. The problem is the follow-up
> questions. How much of it? Which tasks did an agent actually complete on its own? Has quality
> moved as a result? Nobody can answer those, because nobody is measuring them. We built a tool
> that reconstructs the answers from what GitHub already records — **without changing a single
> line in the repositories being tracked.**"

Keep this promise in the client's ear all the way through: **zero changes to their repos,
read-only access.**

### Stop 2 — The pipeline (3 min, whiteboard or the README diagram)

```
config.toml → GitHub API (commits + merged PRs) → classify L1–L5 → metrics.json → dashboard
```

> "One central repository, with a config file listing which repos to follow. CI runs nightly,
> uses a read-only token to pull commits and merged PRs through the GitHub API, assigns an
> autonomy level to each task, and writes a single metrics.json. The dashboard just reads that
> file. The tracked repositories install nothing, change no workflow, and grant no write
> access."

Four points worth landing here:

- Read-only: `Contents: Read-only` + `Pull requests: Read-only`.
- Runs nightly on schedule; also on demand.
- The output is a plain JSON file — auditable, portable, no black box.
- Data never sits on a public page: it is pushed to a **private** data repo and the site sits
  behind **Cloudflare Access** login.

### Stop 3 — How a task gets graded (4 min, Overview tab)

This is the heart of the method. Walk the five-step ladder, highest priority first:

| Priority | Source | In one line |
|---|---|---|
| 1 | PR label `ai-level/L3` | One click in the GitHub UI |
| 2 | Trailer `AI-Level: L3` | Claude Code can write this into the commit automatically |
| 3 | Author mapping | An agent bot account maps to a fixed level |
| 4 | Smart inference | Inferred from PR behaviour — no manual tagging at all |
| 5 | Heuristic | `Co-Authored-By: Claude` → L3, as a floor |

> "Five layers, strongest evidence first. If there is an explicit claim we use the claim; if
> there isn't, we fall back to behaviour. If none of it is there, the task is marked
> 'Unclassified' — we do not quietly assume it was hand-written. That is why there is a
> 'classification coverage' metric: it measures how trustworthy this set of numbers is in the
> first place. Below 80% coverage it turns amber."

Then the levels themselves — L1 Assisted through L5 Full. The single number to highlight:
**L3+ share** — "the proportion of tasks an agent drove to completion. That is the north star
for the whole dashboard."

### Stop 4 — Claims vs behaviour (2 min, still on Overview / Tasks tab)

The credibility argument. Expect this to be the moment a sharp client leans in.

> "A label is only a claim — anyone can type `AI-Level: L4`. So the collector cross-checks it
> against the human activity GitHub has recorded and cannot be argued with. If something claims
> L5 but a person opened the PR, a person reviewed it and a person merged it, we flag it
> ⚠ suspect."

Important nuance to state plainly — it protects you later:

> "We do **not** automatically downgrade it. We surface it for a human to check. And the
> direction is deliberately one-way: visible human involvement can contradict an inflated
> claim, but it cannot catch someone under-reporting."

### Stop 5 — Quality × automation (3 min, Quality tab)

The client's real worry is "does AI-written code break things". This tab is the answer shape:

- Rework share / revert density — how much output goes into fixing rather than advancing
- Changes-requested rate, rework turnaround time
- Rework share per level — **the key chart**: does quality degrade as automation rises?
- Per-repo RAG status (security critical / CI pass rate)

> "The point is not that higher automation is better. The point is whether the rework ratio
> climbs along with the automation level. This chart exists specifically to answer that."

### Stop 6 — Project & delivery view (3 min, Projects + Product tabs)

- Project progress: milestones, slippage, burndown, issue board
- Burndown: remaining tasks ÷ observed completion rate → projected date
- Product & release: roadmap / epics, release readiness

State the limit before they test it:

> "This is a trend projection, not a committed date. When the history is short or the scope has
> changed, the confidence drops automatically — and with no velocity data at all it simply says
> 'unavailable' rather than inventing a date."

### Stop 7 — Traceability (2 min, Tasks tab)

The "prove it" moment. Show that every aggregate number drills down to a real artefact.

- Each row shows its PR (`#N`), or "no PR" for a direct commit
- ⚠ = claim vs behaviour conflict; ⛔ = governance red line; hover shows why
- Filter by level and status, search by title / author / branch / PR

> "Every number here is clickable, all the way down to the actual pull request on GitHub. Not
> one figure on this page comes from nowhere."

### Stop 8 — Governance (2 min, Overview → Executive attention)

> "Alongside measuring autonomy, it catches governance red lines: pushing straight to main,
> committing a .env file, deleting a CI workflow, core modules landing without a second review,
> merging with no review at all, oversized pull requests. Governance is a separate axis — it
> never changes a task's level. The two are reported separately."

### Stop 9 — Close (1 min)

Three sentences to end on:

> "First: zero changes to the tracked repositories, read-only access, so the cost of adopting
> it is almost nothing.
> Second: every number has a provenance you can click through to, and the ones that are proxies
> are labelled as proxies.
> Third: it tells you when it doesn't know. When the data is old or the coverage is thin, it
> writes 'Unknown' rather than showing you a green light."

---

## 4. Five messages they should remember

1. **Zero intrusion** — tracked repos change nothing; read-only token.
2. **Provenance** — every number clicks through to a PR or commit; every assumption is written
   in config and can be audited.
3. **It admits what it doesn't know** — coverage, data health and Unknown states are deliberate
   honesty mechanisms.
4. **It measures the process, not the people** — the metrics are for understanding and
   improving, not appraisal.
5. **Automation and quality are read together** — higher is not automatically better; what
   matters is whether rework climbs with it.

---

## 5. Likely questions — prepared answers

**Q: Do we have to change our repos? Do we install anything?**
> Nothing at all. You provide one read-only token (Contents + Pull requests read access). No
> app to install, no CI changes, no write access.

**Q: Will you be able to read all our code? Does it go to a third party?**
> We do not read code contents. We read metadata — commit titles, branch names, PR status, line
> counts. The resulting metrics.json lives in a private repo, and the dashboard sits behind a
> login gate.

**Q: How do you know the level is accurate? Can people game it?**
> Claims can certainly be gamed, which is exactly why the claim-vs-behaviour cross-check exists
> (see Stop 4). And we do not use these numbers to appraise people — the moment a metric becomes
> a KPI it gets gamed, and then the data is worth nothing. If gaming ever needs to be prevented
> harder, there is a three-stage path: agents on dedicated bot accounts, commit signing split
> across two keys, and session attestation.

**Q: Can you really tell L3 and L4 apart?**
> Honestly: the real difference between L2, L3 and L4 happens inside the coding session, and git
> only records the outcome — so inference is inference, not observation. The accurate approach is
> to have the agent write an `AI-Level` trailer at commit time, because the agent knows best. The
> trailer always wins; inference is the safety net.

**Q: How does your lead time compare to industry benchmarks?**
> Don't compare it directly. We measure "PR opened to merged", not "to production". The card says
> it is a proxy. MTTR is a proxy too. The value in these numbers is the trend, not the comparison.

**Q: Is your revert density the same as DORA's change failure rate?**
> No, and it is worth being careful here. DORA's denominator is deployments; ours is tasks. A
> true CFR needs per-deployment records, and many repos have no Deployments API history at all.

**Q: How often does the data update?**
> Once a day — the authoritative value is the `generated_at` timestamp at the top of the page.
> Past 48 hours it raises a notice that cannot be dismissed, and the management summary switches
> to "Unknown".

**Q: With a small team and few tasks, won't the numbers jump around?**
> Yes, and we say so explicitly. With a dozen or so tasks, one or two tasks will move a median or
> a week-on-week figure substantially. So read the trend line, not a single point; the anomaly
> flags are a prompt to go and look, not a conclusion.

**Q: Does it see code quality itself?**
> No. It measures process metadata — how the work was done and what was claimed. For the full
> picture you connect your CI coverage and security results; we support a target repo publishing
> a small JSON for that.

**Q: What hosting? Is it secure?**
> Cloudflare Pages plus Cloudflare Access — login required to get in, and preview URLs are gated
> too. The data itself sits in a private repo.

**Q: How many repos can it track? Third-party or different orgs?**
> No hard limit; adding one is a single config line. Different orgs can use different tokens —
> each repo can name which token it uses, so there is no need for one broadly-scoped token.

**Q: Can we view it by project or by person?**
> Yes. There are four filters along the top — repo, branch, contributor and time window — and you
> can also group by project owner. Individual tabs can be shared on their own by appending
> `#quality` and so on to the URL.

**Q: Is the dashboard available in other languages?**
> Yes — there is an EN / 繁 toggle in the filter row, and the language is carried in the URL, so
> a link opens in the language you intended.

---

## 6. Do not promise

- Do not say it measures code quality. It measures process metadata.
- Do not present lead time as "to production", or MTTR/CFR as exact DORA metrics.
- Do not commit to a delivery date off the burndown — it is a trend projection.
- Do not offer to show their competitors' or other clients' data as an example.
- Do not promise secret scanning or branch-protection auditing — not detected today.

---

## 7. Status verified on 2026-09-19

- Cloudflare Pages site is **up**, Access login enforced on the main URL.
- Preview subdomain (`main.…pages.dev`) is **also** behind Access — no back door.
- Old GitHub Pages URL returns **404** — correctly disabled.
- Nightly pipeline is running and pushed today.
- **Not verified by me:** the post-login render. Only you can log in — do the Tuesday-night dry
  run.

## 8. Changed on 2026-09-20

- Delivery language switched from Cantonese to **English**; the whole script above was rewritten.
- The dashboard gained an English mode (`?lang=en`). The Tuesday-night dry run must now also
  confirm every tab is fully English, and must hard-refresh to defeat a stale module cache.
- Correction carried over from the Cantonese version: the data-health state was quoted as
  「已過期」, but the dashboard actually renders 「已過時」 / "Stale". The line above now matches
  the screen.
