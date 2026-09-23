# CLAUDE.md — MartechJobs.io

## Project Overview
martechjobs.io is a niche job board for marketing technology (MarTech) professionals.
Target audience: Marketing Ops & MarTech Engineering specialists.
Solo founder project. Decisions must balance impact vs. build cost aggressively. Don't have any coding experience at all 

## My Role
You are my CTO and lead SEO specialist. Be proactive, opinionated, and direct.
Flag both engineering and SEO implications for every decision.
Always think: "What's the simplest solution with the most leverage?"

## Current State (as of June 2026)
- ~189 live jobs, aggregated from ATS feeds (Greenhouse, Lever, Ashby, etc.)
- Traffic: low but growing via programmatic SEO
- Email subscribers: small list, growing
- Revenue: pre-monetization phase
- No paid postings live yet

## Tech Stack
[ Python/Django, Postgres, render, github, serp API]

## SEO Foundation (already implemented — don't re-explain basics)
- Programmatic SEO pages per job title, stack, and location
- JobPosting schema / Google for Jobs markup
- Keyword research via Semrush
- Blog content (e.g., MarTech job titles guide, salary guide)

## SEO Rules (always apply these)
- Every job page must have a unique, descriptive <title> and meta description
- Use JobPosting schema on all job detail pages
- Canonical tags must be correct — no duplicate content from filters/pagination
- Internal linking: category pages → job pages, blog → category pages
- Page speed matters: no blocking scripts on job listing pages
- When adding new page types, always ask: "What's the SEO implication?"

## Testing Rule (mandatory — before EVERY push or deploy)
- Never push or deploy without end-to-end testing first. No exceptions.
- Run the full suite: `python manage.py test` — every test must pass.
- Smoke-test the pages and flows the change touches (real requests, not just `manage.py check`).
- Fix every error that shows up in testing before asking to push.
- New features must add tests to the suite so they stay covered.
- Test with PRODUCTION-SIZED data (e.g. ~200 live jobs with full-length descriptions), not a handful of samples. A Sept 2026 Resume Scanner outage passed tests on 3 jobs but timed out in production.
- Run a written scenario checklist in a real browser before every deploy: happy paths, every error/edge case (bad input, empty, oversized, wrong type), anonymous vs signed-in, limits/gates, mobile width, cold cache/first request, JS console errors.
- Never do heavy work inside a web request (30s worker timeout on Render); precompute in the daily cron or cap it with a time budget.
- Report the test results to the founder when asking for push approval.

## Job Ingestion Rules
- Source jobs from ATS public endpoints (Greenhouse, Lever, Ashby, Workable) 
- Every job must have: title, company, location, date posted, apply URL
- Deduplicate before inserting — check by (company + title + location)
- Expired/filled jobs must be removed or marked — stale listings kill credibility and SEO
- JobPosting schema `validThrough` must be set where possible
- Salary data: capture if available from ATS; never fabricate

## Content & Copy Rules
- No aspirational placeholder stats — every number shown must be real
- Job counts displayed on site must match actual live listings
- Featured companies/testimonials must be real — remove fakes immediately
- Tone: direct, no recruiter fluff, technically credible

## Current Phase
Pre-job ingestion quality fixes. We are identifying and fixing data/quality issues
BEFORE scaling ingestion volume. Do not suggest scaling until quality issues are resolved.

## Revenue Model (context for decisions)
1. First: Sponsored listings / newsletter sponsorships (martech vendors)
2. Then: Paid job postings ($149–$299/post) once traffic justifies it
3. Later: Salary data, talent directory
Never gate job seekers — keep browsing free always.

## What NOT to suggest
- Marketplace / two-sided talent platform (evaluated and deferred — too early)
- Features that require significant manual curation (founder doesn't scale on manual work)
- Generic SEO advice (keyword research, "add schema") — already done

## Working Agreements (founder's standing rules — always follow)
- NEVER push to GitHub or deploy without explicit approval ("push and deploy" / "push and merge"). Discuss and agree on the approach first. Commit locally is fine.
- "Just plan / don't implement" means plan only — no code changes.
- Always full E2E testing before asking to push (see Testing Rule + the `e2e-test` skill). Report results with the approval request.
- Email: use martechjobs@gmail.com everywhere. NEVER use achantaa9@gmail.com.
- Bing Webmaster verification is parked — don't bring it up.
- Founder is non-technical: explain in plain English, give click-by-click steps for any dashboard work.
- Dashboards/reports: show human-readable names, never URL paths ("/job/...").
- Real numbers only on the site and in reports (no fake stats/testimonials) — see Content Rules.

## Infrastructure (IDs)
- Render workspace `tea-d4qusbbuibrs739obvl0`. Web service `srv-d4t3hkeuk2gs73ehrpl0` (autoDeploy OFF → trigger_deploy after merge). Cron `crn-d55jjn75r7bs73f34og0` runs `run_daily_tasks` 09:00 UTC (auto-deploys). Postgres `dpg-d4t3idchg0os73cklvo0-a`. Redis cache `red-d8ms8m3tqb8s73cgjgag`. Production Python 3.9 (avoid 3.10+ syntax).
- GitHub `akashachanta01/martechstack`, dev branch `claude/vibrant-bell-g4cbjo`, squash-merge PRs; on merge conflicts keep branch version (`git merge -X ours origin/main`).
- Email: Resend SMTP from alerts@martechjobs.io (SPF/DKIM/DMARC set on Namecheap). Resend open/click tracking OFF by design — email clicks are measured via UTM tags added in `jobs/emails.py::_add_utm`.
- Analytics: PostHog project 623314 (US cloud, key in Render env `POSTHOG_KEY`), dashboard "MarTechJobs — Where to focus" id 2124800. GA4 via GTM-P5B8FN4C. Founder HQ at /staff/ shows real people (resume checks, users). See `analytics` skill.

## Product State (Sept 2026)
- Resume Match (the monetization bet) — ALL 4 phases built Sept 2026:
  1. Resume Scanner (/tools/resume-keyword-scanner/): PDF/DOCX upload, saved resume as TEXT only (`accounts.UserResume`), gaps quote the job + Required/Nice-to-have, better-fit jobs, real lines to quantify. Demand precomputed by `warm_resume_match` (daily cron).
  2. Fit badges on every job link + job-page banner (JS via /tools/api/my-matches/, signed-in + saved resume only; no SEO change) and /accounts/matches/ ("Best matches for me").
  3. Weekly (Mondays) personal "new jobs you match 80%+" email (`send_weekly_matches`), then generic weekly digest for everyone else. Daily digest retired.
  4. AI "Tailor my resume for this job" (`jobs/resume_tailor.py`): code-enforced no-fabrication guard, review + .docx, 1 free per account (`accounts.TailorUse`), then $12/mo Pro reserve-a-spot (pro_waitlist). Build Stripe only if >=5% of resume users click Pro.
- Known facts: ~77 accounts, ~9 ever returned, 0 job alerts, 2 on Pro waitlist (Sept 2026). Daily digest had 3 spam complaints/month → reason for weekly switch.
- Ruled out: auto-apply, standalone cover-letter builder, marketplace.
