---
name: analytics
description: martechjobs.io analytics — PostHog event taxonomy, dashboard 2124800, HogQL patterns, readable page-type labels. Use when adding tracking, building charts, or answering "how is X doing".
---

# Analytics for martechjobs.io

## Where things live
- `window.mtjTrack(event, params)` in `jobs/templates/jobs/base.html` pushes to GTM dataLayer AND PostHog.
  Every event auto-gets `page_type` (Django url_name) and `came_from` (previous page_type, external source like
  google/linkedin, or direct). NEVER send URL paths, names or emails in params.
- PostHog loads async only when `POSTHOG_KEY` is set, skips staff users, identifies signed-in users by id+email.
- PostHog project 623314 (US). Dashboard "MarTechJobs — Where to focus": id 2124800. PostHog MCP tool is pre-allowed.

## Event taxonomy
apply_click, job_search, newsletter_subscribe, signup_click, signup_completed (one-shot via session flag set in
accounts/signals.py), job_saved, pro_waitlist_join, check_resume_click, ats_check_submit, ats_check_result,
ats_gate_shown, ats_signup_click, ats_more_match_click, resume_uploaded, resume_deleted, employer_cta_click,
post_job_start, post_job_submit, post_job_completed, content_to_jobs_click, tool_used,
Resume Match: resume_uploaded, resume_deleted, ats_error_shown (every error a visitor sees: outage early-warning),
fit_badge_job_click, fit_banner_click, my_matches_job_click, my_matches_check_click, tailor_click, tailor_success,
tailor_error, tailor_download, pro_gate_shown, pro_preorder_click (the Pro decision metric: build Stripe only if
>=5% of resume users click). $pageview carries page_type + came_from (registered super properties).
Emails: links auto-tagged utm_source=email&utm_campaign=<template name> (jobs/emails.py::_add_utm).

## Reports: founder wants human-readable names, never "/" paths
Map page_type → label in SQL, e.g. job_list→Homepage, job_detail→Job page, tool_detail→Tool jobs page,
title_jobs→Job-title page, seo_tool_loc→Location + tool page, seo_loc_only→Location page, post_detail→Blog post,
blog_list→Blog home, blog_*→Blog section, salary_guide/role_salary→Salary page, for_employers→For employers,
post_job→Post a job form, tools_hub→Free tools hub, resume_scanner→Resume checker, account*→Account area.
Sources from sessions.`$entry_referring_domain`/`$entry_utm_source` → Google, Direct / bookmark, Email newsletter...

## HogQL gotchas (PostHog SQL insights)
- Column aliases can't contain `%` → use "(pct)".
- `substring(s, start, len)` needs 3 args.
- UNION ALL branches must have identical types → wrap numbers in `toFloat()`.
- sessions table uses `$start_timestamp` (not min_timestamp), `$is_bounce`, `$session_duration`, `$pageview_count`.
- Verify each saved insight with `insight-query` after creating it.
- Founder HQ (/staff/) answers "who" (names/emails) — PostHog/GA answer "how many".
