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
