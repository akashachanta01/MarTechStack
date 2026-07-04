# MarTechJobs — Engineering Backlog

Prioritized list of known issues and improvements. Keep this in sync with what
ships. Newest decisions at the top of each section.

---

## FOUNDER OPS / DISTRIBUTION

- [ ] **LinkedIn auto-posting for blog articles (Zapier)** — plumbing is live
  (`/blog/feed/` RSS announces every published post); just needs the no-code
  bridge connected (~10 min):
  1. zapier.com → Create Zap → Trigger: "RSS by Zapier → New Item in Feed",
     feed URL `https://martechjobs.io/blog/feed/`
  2. Action: "LinkedIn Pages → Create Company Update" (must be page admin);
     text = `{{Title}}` + `{{Description}}` + link `{{Link}}`
  3. Turn on. Free tier (100 tasks/mo) covers ~1-3 posts/week easily.
  Alternatives: Make.com or dlvr.it. Keep the manual habit: reshare the best
  data pieces from the personal profile with one added sentence — personal
  posts get ~10x company-page reach.
- [ ] **IndexNow one-time setup** — set `INDEXNOW_KEY=<random 32-char hex>` in
  Render env (web + cron); verify site in Bing Webmaster Tools + submit
  sitemap. Until then the daily `ping_indexnow` step politely skips.
  (ChatGPT search runs on Bing's index.)
- [ ] **Rotate Resend API key + DB password** — both appeared in a shared
  screenshot; treat as burned. Resend: dashboard → new key → update
  `EMAIL_HOST_PASSWORD` → delete old. DB: rotate in Render Postgres settings.
- [ ] **Ahrefs API quota** — at 0 units; recheck next cycle and pull baseline
  (DR, referring domains, AI-citation counts via `ai-responses-count`).
- [ ] **Monthly AEO scoreboard** — ask ChatGPT/Perplexity/Gemini "best job
  boards for marketing operations roles"; log whether martechjobs.io appears.
- [ ] **Community distribution** — MO Pros Slack intro post (draft written),
  10 backlink outreach emails (ChiefMartec, MarTech Alliance, …), Antara
  (Mavlers) recruiter email (draft written, send to Antara@mavlers.com).

---

## TECH DEBT

### Migration history baseline reset (planned)
**Problem:** Production DB is ahead of the migration history. Models in `jobs`
have columns/models the migration files never captured (`Subscriber`,
`ActiveJob`/`UserSubmission` proxies, `is_featured`, `is_pinned`, `slug`,
`salary_range`, `work_arrangement`, several indexes, etc.). They already exist
in prod, added early via hand-written minimal migrations. This produces the
persistent deploy warning:

> Your models in app(s): 'jobs' have changes that are not yet reflected in a migration.

**Why we must NOT just run makemigrations on Render:** it would generate a
catch-up migration that tries to `CREATE` columns that already exist → deploy
crashes with `column already exists`.

**Plan (careful, low-risk, do in a quiet window):**
1. Locally, point at a DB snapshot that matches prod schema.
2. `makemigrations jobs` to generate the full catch-up migration (the
   `0010_...` Django keeps proposing).
3. On prod shell: `python manage.py migrate jobs 0010 --fake` so Django records
   it as applied WITHOUT touching the (already-correct) schema.
4. Verify `migrate --plan` is clean and the deploy warning is gone.
5. Optionally squash 0001–0010 into a single baseline later for cleanliness.

**Risk:** Must confirm the generated migration exactly matches prod schema
before `--fake`. If it proposes an actual schema change (not just catch-up),
stop and reconcile first. Test the `--fake` on a prod clone if possible.

**Priority:** Medium. Not urgent — current deploys work fine; this just removes
fragility for future real migrations.

---

## SCREENER QUALITY

> ⚠️ DEFERRED ON PURPOSE: the two refactors below change which jobs get
> approved. They must be done WITH the `score_screener` example suite in front
> of us (and ideally new test cases), not in a bulk sweep — a wrong tweak
> silently lets junk in or rejects real roles. Highest-care items in the repo.
- [ ] **Title gate / description fallback conflation** (`screener.py:173-194`):
  generic titles that pass the keyword gate weakly skip GPT entirely. Refactor
  to: `if (has_keyword or desc_signal): send to GPT` — never auto-approve a
  generic title without GPT looking at the JD.
- [ ] **Vendor trap bypass too permissive** (`screener.py:151-162`): bypass
  fires on any tool-name-in-title incl. "Salesforce", letting vendor-employee
  roles through. Restrict bypass to specialist MarTech tools only.
- [x] **Adobe hack fires on Magento** — DONE. Removed "magento" from the
  post-GPT Adobe-Experience-Cloud trigger (Magento is e-commerce, not MarTech).
- [ ] **No RevOps hard-reject** — NEEDS PRODUCT DECISION, not a code fix. The
  screener prompt excludes RevOps, yet there's a programmatic `revenue-
  operations-manager` TITLE_JOBS page. Resolve the contradiction first (do we
  want RevOps or not?) before hard-coding a gate.
- [~] **Screener error handling** — RE-EVALUATED, not a bug. Missing key / crash
  → status "pending", and pending always means `is_active=False` (not live). So
  unreviewed jobs already stay out of public view; they queue for human review,
  which is the desired fail-safe. No change.

## JOB FETCHING / DATA QUALITY

- [x] **Ashby description is placeholder** — DONE. Now uses the real
  `descriptionHtml`/`descriptionPlain` from Ashby's job-board API (cleaned via
  `clean_html_description`), falling back to the URL pointer only if absent.
- [x] **Workday description is title-only** — DONE (audit round 4). Now fetches
  the real JD from the per-job CXS detail endpoint; postings with no fetchable
  body are skipped (`Workday:no_description` stat). Verify the stat in cron
  logs looks sane after a few runs.
- [x] **Empty-description fallback** — DONE. `job_detail.html` shows a clear
  "available on the employer's site → Apply Now" message when description is
  blank, so a page never renders an empty content block.
- [x] **Tool auto-creation allows junk** — DONE. Root cause was two whitelist
  bypasses: (1) `post_job` (`views.py`) let user free-text mint arbitrary Tool
  rows, (2) ingestion `_resolve_tool` fell back to attaching jobs to existing
  non-canonical tools. Both now route through `resolve_tool_name` and drop
  anything not in the catalog. Added `prune_noncanonical_tools` command
  (dry-run default) to delete the historical junk Tool rows/pages.
- [x] **Greenhouse multi-region** — already handled: the dispatch regex matches
  `greenhouse.io`, `eu.greenhouse.io`, and `job-boards.greenhouse.io`.
- [x] **og:title / og:description match the page** — DONE. Added per-page
  `og_title`/`og_desc` to category, tool_detail, title_jobs, seo_landing,
  all_jobs, salary_guide, blog_list, company_detail (job_detail, post_detail,
  for_employers already had them). They now mirror each page's title/meta
  instead of the global default.

## FEATURES (tracked with the accounts/dashboard build)

- [x] **Email subscribe has no verification** — DONE. Double opt-in shipped:
  signups land in `PendingSubscriber` and are only promoted to `Subscriber` on
  the emailed confirmation link; unsubscribe is a soft-delete suppression.
- [ ] **post_job missing function/category field** (`views.py`): user-posted
  jobs default to `function="other"` and never appear on category pages. Add a
  function selector. Fold into the post-job/accounts work.

## PAYMENTS / MONETIZATION (Stripe — DEFERRED until paid postings launch)

> Not launching paid postings anytime soon, so these are parked. Do them BEFORE
> the first real paid post goes live — they only matter once money changes hands.
- [ ] **Stripe checkout has no error handling** (`views.py:~1085`):
  `stripe.checkout.Session.create()` is not wrapped in try/except. A network
  blip or bad param → the paying user sees a raw 500 instead of a friendly
  "couldn't start checkout, try again" message. Wrap it and redirect back to
  `post_job` with a message.
- [ ] **Stripe webhook race condition** (`views.py:~1112`): duplicate webhook
  deliveries for the same `checkout.session.completed` could approve the job and
  fire alert emails twice. Add `select_for_update()` + an idempotency guard
  (e.g. only approve `if not job.is_featured`) so the approval runs exactly once.
- [ ] **Salary cache not busted on paid approval** (`views.py:~1113`): the
  webhook clears `popular_tech_stacks_v4` and `available_countries_v2` but NOT
  `salary_guide_data_v2`. A new paid job with salary data won't show in the
  salary guide for up to 1 hour. Add the missing `cache.delete`.
- [ ] **No logging on paid-job approval** (`views.py:~1112`): add `logger.info`
  when a webhook auto-approves a job, so there's an audit trail if a payment
  doesn't result in a live listing.

## SEO

- [x] **Expired job URLs return 410 Gone** — DONE. GSC showed 1,291 hard 404s +
  247 Soft 404s from expired listings (ingested → indexed → purged/demoted).
  `job_detail` now returns HTTP 410 (with a "no longer available → browse
  similar" page) for both deleted rows and demoted/closed jobs, so Google
  de-indexes them promptly instead of wasting crawl budget. Run "Validate Fix"
  on both GSC reports after deploy.
- [ ] **Crawled – currently not indexed: 378** (GSC): thin/low-value pages
  Google chose not to index. Not an error — a content-quality / internal-linking
  project. Investigate which URL types dominate this bucket before acting.
- [x] **tool_detail `rel=prev/next`** — already present (`tool_detail.html:7-9`).
  The audit flagged this in error.
- [x] **robots.txt filter URLs** — DONE. Disallowed `?q=`, `?l=`, `?sort=`
  (and `&` variants). `?page=` left crawlable on purpose — paginated pages carry
  rel=prev/next and aid discovery.
- [ ] **Category FAQ schema is boilerplate**: same generic Q&A on every
  category. Low priority — not broken, just generic. Leave for now.

## UX

- [x] **Location defaults to "Remote"** — DONE. Changed the `|default` on every
  listing/detail template from "Remote" to "Not specified" (honest when the
  location field is genuinely empty).
- [x] **State rollup** — DONE (the issue raised directly). State pages now match
  both the full name AND the USPS code in stored locations, so "San Francisco,
  CA" jobs correctly appear on `/california/jobs/`. Fixed at query time in
  `seo_landing_page` via a new `US_STATE_ABBR` map — works on existing data
  without re-ingesting.
- [~] **Salary parsing assumes annual** (`models.py`): RE-EVALUATED — low risk.
  The parser already detects hourly (`/hr`, `per hour`, …) and filters results
  to a plausible 10k–2M annual band, so stray tokens are dropped. Leaving as-is;
  revisit only if real mis-parses surface.

## OBSERVABILITY (nice-to-have)

- [x] Bare `except: pass` in `fetch_jobs.py` SerpAPI call — DONE (now catches
  `requests.RequestException` and logs). `update_logos.py` still TODO.
- [x] **CompanySource auto-disable now visible** — DONE. Prints a ⚠ warning line
  naming the board when it auto-disables (email alert still a future nicety).
- [x] **Per-source progress logging** — DONE. The poll loop prints
  `[idx/total] ats:token → +N` per board so a long `--sources-only` run is
  visibly alive.
