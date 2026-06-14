# MarTechJobs — Engineering Backlog

Prioritized list of known issues and improvements. Keep this in sync with what
ships. Newest decisions at the top of each section.

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

- [ ] **Title gate / description fallback conflation** (`screener.py:173-194`):
  generic titles that pass the keyword gate weakly skip GPT entirely. Refactor
  to: `if (has_keyword or desc_signal): send to GPT` — never auto-approve a
  generic title without GPT looking at the JD.
- [ ] **Vendor trap bypass too permissive** (`screener.py:151-162`): bypass
  fires on any tool-name-in-title incl. "Salesforce", letting vendor-employee
  roles through. Restrict bypass to specialist MarTech tools only.
- [ ] **Adobe hack fires on Magento** (`screener.py:313-322`): post-GPT
  injection of "Adobe Experience Cloud" on a "magento" match is wrong; Magento
  is e-commerce, not MarTech.
- [ ] **No RevOps hard-reject** in `_quick_kill()`: RevOps excluded only by GPT
  prompt; add a fast-fail gate for "revops"/"revenue operations".
- [ ] **Screener error handling backwards** (`screener.py:196-203`): missing
  API key → score 50 (pending), crash → score 25. Unreviewed jobs should fail
  closed (stay out of live), not drift toward approval.

## JOB FETCHING / DATA QUALITY

- [ ] **Ashby description is placeholder** (`fetch_jobs.py:478`): stores
  "Full details at {url}" instead of the real JD. Detail page shows nothing.
- [ ] **Workday description is title-only** (`fetch_jobs.py:617`): same problem.
- [ ] **Empty-description fallback**: when an ATS returns no JD, show a clear
  "View full description on employer site" message instead of a blank section.
- [ ] **Tool auto-creation allows junk** (`fetch_jobs.py:749-757`): GPT stack
  items not in the catalog become Tool rows ("crm", "data platform"). Restrict
  to the canonical catalog whitelist.
- [ ] **Greenhouse multi-region** (`fetch_jobs.py:293`): also handle
  `job-boards.greenhouse.io` subdomain.

## FEATURES

- [ ] **Email subscribe has no verification** (`views.py:905-947`): any email
  can subscribe; no confirmation link. Add token-based double opt-in
  (`is_confirmed=False` until clicked).
- [ ] **post_job missing function/category field** (`views.py:843-879`):
  user-posted jobs default to `function="other"` and never appear on
  /engineering-jobs/, /operations-jobs/, /data-jobs/. Add a function selector.

## SEO

- [ ] **tool_detail.html missing `rel=prev/next`**: the only paginated template
  still lacking it (all_jobs, category, title_jobs, seo_landing have it).
- [ ] **robots.txt doesn't block filter URLs** (`config/urls.py`): `/?q=...`,
  `?page=...` combinations waste crawl budget. Add disallow or canonicalize.
- [ ] **Category FAQ schema is boilerplate**: same generic Q&A on every
  category; add unique value or drop it.

## UX

- [ ] **Location defaults to "Remote"** (`job_list.html:568`,
  `all_jobs.html:292`): misleading when location is just missing. Change default
  to "Location not specified".
- [ ] **Location normalization misses "State, United States" format**
  (`models.py:14-22`): only abbreviates states preceded by ", ".
- [ ] **Salary parsing assumes annual** (`models.py:154`): bare "150" → $150k;
  wrong for hourly/contract. Require explicit `$150k` / `$150/hr` syntax.

## OBSERVABILITY (nice-to-have)

- [ ] Replace bare `except: pass` in `fetch_jobs.py` (lines ~227, ~397) and
  `update_logos.py` with specific exception types + logging.
- [ ] Alert the founder (email) when a CompanySource auto-disables after 5
  empty polls, so silent source loss is visible.
- [ ] **Per-source progress logging in `poll_company_sources`**
  (`fetch_jobs.py:385-407`): the loop runs silently between the
  "Direct-polling N sources..." header and the final summary — a full
  `--sources-only` run can take 10-30 min (paid GPT screen + rate-limited
  Nominatim geocode per new job) with zero output, looking hung. Print a
  per-source line, e.g. `[12/89] greenhouse:acme → +3`, so the run is
  visibly alive in the Render shell. Small change, high operator value.
