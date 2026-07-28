# Phase 2 — Cloudflare Pages + Access Design

**Date:** 2026-07-28
**Status:** Approved by user (this session), pending implementation plan.

## Goal

Put the dashboard online at a stable URL with **real authentication**, so the owner and
two named colleagues can view live data from any device without running anything locally.

URL: `https://management-dashboard-emj.pages.dev` (default Pages subdomain; a custom domain
can be attached later without changing anything in this design).

## Decision: this supersedes the "no third-party services" constraint

Spec `2026-07-27-dashboard-enhancements-design.md` (rev 3) and the Phase 1 plan declared
**"No third-party services"** as a hard constraint. The user has explicitly reversed that
decision in this session: Cloudflare is now in scope. Consequences accepted by the user:

- `metrics.json` (containing private-repo commit titles, author logins, branch names)
  will be **stored on Cloudflare Pages**, gated behind Cloudflare Access — not public.
- Cloudflare Access becomes the only authentication layer for the hosted dashboard.
  The GitHub-permission path (private data repo + local server) continues to work
  unchanged as a fallback.

## Architecture

```
Daily 05:00 HKT — existing collect.yml
  collect → /tmp/metrics.json
    ├─▶ push to private data repo  wing-csi/ManagementDashboard-data   (existing, unchanged)
    └─▶ NEW: copy into docs/data/ (CI runner only) and
             wrangler pages deploy docs/ → Cloudflare Pages project "management-dashboard"
                                     │
Browser ─▶ https://management-dashboard-emj.pages.dev
             └─▶ Cloudflare Access login page (One-time PIN by email)
                   allowed: wingpoon1990@gmail.com,
                            wing.poon@chinasofti.com,
                            Shane.chan@chinasofti.com
                                     │
                   Dashboard (unchanged code) fetches ./data/metrics.json
```

The frontend needs **zero code changes**: it already fetches the relative path
`./data/metrics.json`, and Access protects the whole hostname — including that JSON URL
and all preview URLs. An unauthenticated request to any path gets the Access login page.

## Components

### 1. Cloudflare side (one-time manual setup, ~10 min, guided)

Performed by the user in the Cloudflare dashboard (agent provides step-by-step
instructions; the API token value is never handled by the agent):

1. Create Pages project `management-dashboard` via Direct Upload (no Git integration,
   because the deployed content includes `metrics.json` which is deliberately not in
   git). The initial upload is a **single placeholder file** — no real data.
2. Enable Zero Trust (free plan, pick a team name).
3. Create an Access application covering **both** `management-dashboard-emj.pages.dev`
   (production) and `*.management-dashboard-emj.pages.dev` (preview URLs).
4. Access policy: Allow → Include → Emails: the three addresses above.
   Login method: **One-time PIN only** (no IdP, nothing to install).
5. Create an API token with the **"Cloudflare Pages — Edit"** template (least privilege),
   note the Account ID, and add both to the hub repo's GitHub Actions secrets:
   `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`.

**Ordering constraint (security):** the first CI deploy contains real `metrics.json`,
so steps 1–4 must be completed — and the unauthenticated-request check verified to show
the Access login page — **before** the secrets are set and any CI deploy is triggered.
This guarantees the private data is never reachable without login, even briefly.

### 2. CI change (code, in this repo)

`collect.yml` gets one new step after "Publish metrics to private data repo":

- Guard: if `CLOUDFLARE_API_TOKEN` or `CLOUDFLARE_ACCOUNT_ID` secrets are missing,
  **fail loudly** with a message naming the missing secret — never skip silently.
- `cp /tmp/metrics.json docs/data/metrics.json` (CI runner workspace only — the file
  remains gitignored and is never committed to this public repo; the existing guard
  test keeps enforcing that invariant).
- `npx wrangler@4 pages deploy docs --project-name=management-dashboard --branch=main`
  (pinned major version; `--branch=main` marks it as the production deployment).

Manual runs keep working: the workflow already has `workflow_dispatch`, so the first
deploy can be triggered immediately after secrets are set.

### 3. Dashboard code

No changes.

## Error handling

- Missing Cloudflare secrets → explicit CI failure (guard step), visible in Actions.
- Wrangler deploy failure → step fails, workflow shows red; data-repo publish has already
  completed by then, so the GitHub fallback path still has fresh data.
- Access misconfiguration (e.g. app not covering preview URLs) is caught by the
  verification checklist below before the setup is declared done.

## Risks / accepted trade-offs

- Private commit metadata lives on Cloudflare (behind Access). Accepted explicitly.
- The Access email allowlist is the **single** auth layer; there is no second login.
  The Cloudflare account itself must have 2FA enabled.
- API token is Pages-edit only: leak/expiry affects deploys, nothing else.
  Token expiry surfaces as a loud CI failure, same as `DATA_REPO_PAT` expiry.

## As-built notes (2026-07-28, Cloudflare setup)

Two things differ from this design as originally written. Both are recorded here rather
than silently absorbed:

1. **Hostname carries a suffix.** `management-dashboard.pages.dev` was already taken
   globally, so Cloudflare assigned **`management-dashboard-emj.pages.dev`**. The Pages
   *project* name is still `management-dashboard`, so the workflow's
   `--project-name=management-dashboard` is unaffected. All docs now use the real host.
2. **Access is two applications, not one.** The Cloudflare dashboard locks the
   Pages-managed app's destination to the preview wildcard, so:
   - `*.management-dashboard-emj.pages.dev` (previews) — app auto-created by the Pages
     "Restrict previews" toggle, policy **"Allow Members - Cloudflare Pages"** (account
     members only, i.e. currently just the account owner).
   - `management-dashboard-emj.pages.dev` (production) — separate self-hosted app,
     policy **"Dashboard viewers"** = the three allowlisted emails, One-time PIN.

   Consequence: the two colleague addresses can open **production only**, not preview
   URLs. That is more restrictive, not less, and the CI deploys with `--branch=main`
   (production) so no preview URL is produced by this pipeline. If preview access is
   ever wanted for them, attach the "Dashboard viewers" policy to the preview app too.

Access team domain: `summer-mud-0e86.cloudflareaccess.com`.

## Verification checklist (definition of done)

- [x] Unauthenticated `https://management-dashboard-emj.pages.dev/` → Access login page, not the dashboard. **Verified 2026-07-28: 302 → `summer-mud-0e86.cloudflareaccess.com`.**
- [x] Unauthenticated `https://management-dashboard-emj.pages.dev/data/metrics.json` → blocked the same way. **Verified 2026-07-28: 302 → same login.**
- [ ] Login with an allowlisted email (OTP) → dashboard renders with real data, no console errors.
- [ ] An email outside the allowlist cannot get in.
- [ ] `workflow_dispatch` run of `collect` is green end-to-end and the site shows the fresh `generated_at`.
- [ ] `docs/data/metrics.json` still untracked in this public repo (existing guard test passes).

## Out of scope

- Custom domain (can be attached to the Pages project later).
- Removing the public repo's historical `metrics.json` git history (pre-existing
  follow-up, unchanged by this phase).
- Any change to collector, classification, or dashboard rendering logic.
