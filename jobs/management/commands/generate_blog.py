import os
import json
import random
from typing import Optional
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from openai import OpenAI
from jobs.models import BlogPost

# Prioritized topic queue — worked through in order, not randomly.
# Tier 1: Company careers guides (branded, low KD, high volume)
# Tier 2: Role/skill guides
# Tier 3: Salary guides
TOPIC_QUEUE = [
    # Tier 0 (FRONT OF QUEUE): hot-topic data + opinion pieces for the AI in
    # MarTech section — the founder's most shareable LinkedIn material, so they
    # publish first. data_piece entries get a LIVE stats digest computed from
    # the DB at generation time and may cite ONLY those numbers (site rule:
    # every number shown must be real).
    {"type": "data_piece", "topic": "Which MarTech Skills Appear Most in Job Listings Right Now", "keyword": "most in demand martech skills", "angle": "Rank the platforms/skills by how often they appear in our live listings. Lead with the #1. What the distribution says about where the market is heading."},
    {"type": "data_piece", "topic": "The AI Skills Gap in MarTech Job Descriptions", "keyword": "ai skills gap martech", "angle": "Contrast how many live listings mention AI against the total, and what that ratio means: employers are ahead of (or behind) candidates. What 'AI experience' requirements look like in practice and how a candidate closes the gap."},
    {"type": "data_piece", "topic": "What Employers Actually Mean When They Ask for 'AI Experience'", "keyword": "ai experience job requirements marketing", "angle": "Decode the phrase using the real patterns in our listings: platform AI features (Einstein, predictive scoring), prompt fluency, AI governance. Give candidates concrete ways to demonstrate each."},
    {"type": "data_piece", "topic": "What Our Live MarTech Job Listings Taught Me About Hiring in the AI Era", "keyword": "martech hiring trends ai era", "angle": "A founder's field-notes piece: the patterns across ALL our live listings — which functions dominate, remote share, platform demand, how often AI appears. Use the exact live-listing count from the data digest in the title and intro (e.g. 'What 300 MarTech Job Posts...')."},
    {"type": "data_piece", "topic": "The One Skill That Shows Up in Every Senior MarTech Listing", "keyword": "senior martech skills", "angle": "Use the senior-role stats in the digest: what share of live listings are senior, and which platforms/skills dominate those. Build the piece around the top one and why it keeps appearing at the senior level."},
    {"type": "data_piece", "topic": "Salary Signals: What AI Skills Add to MarTech Pay", "keyword": "ai skills salary martech", "angle": "Use the salary-transparency stats provided (share of listings with published ranges, median range). Be honest that AI-skill premium data is early; frame directional signals, not fake precision."},
    {"type": "ai_martech", "topic": "The MarTech Career Ladder, Redrawn for the AI Era", "keyword": "martech career path ai", "angle": "An original framework: the old ladder (specialist → admin → manager) vs the new one (tool operator → systems designer → AI orchestrator → architecture/governance). Name what to learn at each rung."},
    {"type": "ai_martech", "topic": "Stop Learning Tools, Start Learning Systems", "keyword": "martech skills strategy", "angle": "Opinion piece with a spine: tool certifications depreciate, systems thinking compounds. Data models, integration patterns, and lifecycle logic transfer across every platform; the tool-of-the-month does not. Concrete examples of 'systems' skills and how to build them."},
    {"type": "ai_martech", "topic": "MarTech Roles That Will Exist in 2028", "keyword": "future martech roles 2028", "angle": "Grounded prediction piece: extrapolate from real, present hiring signals (CDP engineering growth, AI governance requirements, journey orchestration) to roles like AI Campaign Orchestrator, Marketing Data Governance Lead, GTM Systems Architect. Clearly label as prediction; explain the signal behind each."},
    {"type": "ai_martech", "topic": "Red Flags in AI-Era MarTech Job Descriptions", "keyword": "martech job description red flags", "angle": "Practical, shareable checklist: 'AI experience' with no specifics, one-person-stack roles disguised as 'AI-leveraged efficiency', tool soup with no seniority match, AI mandates with no data foundation. For each red flag: why it matters and the interview question that exposes it."},
    # Tier 1: Company careers guides — ordered by Ahrefs vol/KD
    # hubspot careers: 14K vol, KD 4
    {"type": "company_careers", "company": "HubSpot", "tool_slug": "hubspot", "keyword": "hubspot careers", "volume": 14000},
    # klaviyo careers: 2.4K vol, KD 2
    {"type": "company_careers", "company": "Klaviyo", "tool_slug": "klaviyo", "keyword": "klaviyo careers", "volume": 2400},
    # braze careers: 1.6K vol, KD 0
    {"type": "company_careers", "company": "Braze", "tool_slug": "braze", "keyword": "braze careers", "volume": 1600},
    # amplitude careers: 1.1K vol, KD 4
    {"type": "company_careers", "company": "Amplitude", "tool_slug": "amplitude", "keyword": "amplitude careers", "volume": 1100},
    {"type": "company_careers", "company": "Mixpanel", "tool_slug": "mixpanel", "keyword": "mixpanel careers", "volume": 300},
    # marketo careers: 40 vol, KD 3 — low vol but hyper-targeted audience
    {"type": "company_careers", "company": "Marketo", "tool_slug": "marketo", "keyword": "marketo careers", "volume": 40},
    {"type": "company_careers", "company": "Iterable", "tool_slug": "iterable", "keyword": "iterable careers", "volume": 200},
    {"type": "company_careers", "company": "Tealium", "tool_slug": "tealium", "keyword": "tealium careers", "volume": 150},
    {"type": "company_careers", "company": "mParticle", "tool_slug": "mparticle", "keyword": "mparticle careers", "volume": 100},
    # Tier 2: Role/skill guides — Ahrefs data: marketing operations jobs 450 KD0,
    # marketing automation jobs 200 KD1, martech jobs 200 KD0, cdp jobs 70 KD0
    {"type": "role_guide", "topic": "Marketing Operations Manager", "keyword": "marketing operations jobs", "tool_slug": None},
    {"type": "role_guide", "topic": "Marketing Automation Specialist", "keyword": "marketing automation jobs", "tool_slug": None},
    {"type": "role_guide", "topic": "MarTech Specialist", "keyword": "martech jobs", "tool_slug": None},
    {"type": "role_guide", "topic": "Marketing Technology Manager", "keyword": "marketing technology jobs", "tool_slug": None},
    {"type": "role_guide", "topic": "CDP Specialist", "keyword": "cdp jobs", "tool_slug": None},
    {"type": "role_guide", "topic": "Salesforce Administrator", "keyword": "salesforce admin jobs martech", "tool_slug": "salesforce"},
    {"type": "role_guide", "topic": "Marketing Data Analyst", "keyword": "marketing data analyst jobs", "tool_slug": None},
    {"type": "role_guide", "topic": "Email Marketing Manager", "keyword": "email marketing manager jobs martech", "tool_slug": None},
    # Tier 3: Salary guides — keywords confirmed via Ahrefs Keyword Explorer
    # marketing automation specialist salary: 200 vol, KD 2
    {"type": "salary_guide", "topic": "Marketing Automation Specialist Salary", "keyword": "marketing automation specialist salary", "tool_slug": None},
    # marketing operations salary: 60 vol, KD 0
    {"type": "salary_guide", "topic": "Marketing Operations Salary", "keyword": "marketing operations salary", "tool_slug": None},
    # hubspot admin salary: 20 vol, KD 0 (parent: hubspot administrator salary)
    {"type": "salary_guide", "topic": "HubSpot Administrator Salary", "keyword": "hubspot admin salary", "tool_slug": "hubspot"},
    # salesforce marketing cloud salary: 20 vol, KD 0
    {"type": "salary_guide", "topic": "Salesforce Marketing Cloud Salary", "keyword": "salesforce marketing cloud salary", "tool_slug": "salesforce"},
    # klaviyo specialist salary: estimated, hyper-targeted
    {"type": "salary_guide", "topic": "Klaviyo Specialist Salary", "keyword": "klaviyo specialist salary", "tool_slug": "klaviyo"},
    # Tier 4: GSC 0-click high-impression queries — site ranks but no dedicated page
    # "marketing technology consultant" 132 impressions, "martech consultant" 123,
    # "martech developer" 113, "martech solutions" 113 — all 0 clicks
    {"type": "role_guide", "topic": "MarTech Consultant", "keyword": "martech consultant", "tool_slug": None},
    {"type": "role_guide", "topic": "MarTech Developer", "keyword": "martech developer", "tool_slug": None},
    {"type": "role_guide", "topic": "Marketing Technology Consultant", "keyword": "marketing technology consultant", "tool_slug": None},
    {"type": "role_guide", "topic": "MarTech Solutions Architect", "keyword": "martech solutions", "tool_slug": None},
    # Tier 5: GSC 0-click queries 100+ impressions (3-month data)
    {"type": "role_guide", "topic": "MarTech Recruitment Guide", "keyword": "martech recruitment", "tool_slug": None},
    {"type": "role_guide", "topic": "MarTech Specialist", "keyword": "martech specialist", "tool_slug": None},
    {"type": "role_guide", "topic": "Marketing Technology Analyst", "keyword": "marketing technology analyst jobs", "tool_slug": None},
    {"type": "company_careers", "company": "Optimizely", "tool_slug": "optimizely", "keyword": "optimizely careers", "volume": 112},
    # Tier 6: International geo-targeted guides — capture non-US search demand
    # (GA shows meaningful India/UK/SG/DE traffic). Each links to the matching
    # country landing page so the blog feeds the programmatic country pages.
    {"type": "location_guide", "topic": "MarTech Jobs in India", "keyword": "martech jobs in india", "location_slug": "india", "location_name": "India"},
    {"type": "location_guide", "topic": "MarTech Jobs in the UK", "keyword": "martech jobs uk", "location_slug": "united-kingdom", "location_name": "the United Kingdom"},
    {"type": "location_guide", "topic": "MarTech Jobs in Singapore", "keyword": "martech jobs singapore", "location_slug": "singapore", "location_name": "Singapore"},
    {"type": "location_guide", "topic": "MarTech Jobs in Germany", "keyword": "martech jobs germany", "location_slug": "germany", "location_name": "Germany"},
    {"type": "location_guide", "topic": "MarTech Jobs in Canada", "keyword": "martech jobs canada", "location_slug": "canada", "location_name": "Canada"},
    {"type": "location_guide", "topic": "Marketing Operations Jobs in India", "keyword": "marketing operations jobs india", "location_slug": "india", "location_name": "India"},
    # Tier 7: India salary guides in INR/LPA — the format Indian job seekers
    # actually search in ("salesforce admin salary india"). Huge volume, thin
    # competition, and India is our #2 traffic market. Live listings skew
    # heavily SFMC/Marketo/AEM/Salesforce, matching these exactly.
    {"type": "intl_salary_guide", "topic": "Salesforce Administrator Salary in India", "keyword": "salesforce admin salary india", "market": "India", "currency": "INR (express figures in lakhs per annum, e.g. ₹8–14 LPA)", "cities": "Bengaluru, Mumbai, Hyderabad, Pune, Gurgaon, Chennai", "location_slug": "india"},
    {"type": "intl_salary_guide", "topic": "Salesforce Marketing Cloud (SFMC) Salary in India", "keyword": "sfmc salary india", "market": "India", "currency": "INR (express figures in lakhs per annum, e.g. ₹10–18 LPA)", "cities": "Bengaluru, Mumbai, Hyderabad, Pune, Gurgaon", "location_slug": "india"},
    {"type": "intl_salary_guide", "topic": "Marketo Salary in India", "keyword": "marketo salary india", "market": "India", "currency": "INR (express figures in lakhs per annum)", "cities": "Bengaluru, Mumbai, Hyderabad, Pune", "location_slug": "india"},
    {"type": "intl_salary_guide", "topic": "Marketing Operations Salary in India", "keyword": "marketing operations salary india", "market": "India", "currency": "INR (express figures in lakhs per annum)", "cities": "Bengaluru, Mumbai, Delhi NCR, Hyderabad, Pune", "location_slug": "india"},
    {"type": "intl_salary_guide", "topic": "AEM Developer Salary in India", "keyword": "aem developer salary india", "market": "India", "currency": "INR (express figures in lakhs per annum)", "cities": "Bengaluru, Hyderabad, Pune, Noida", "location_slug": "india"},
    {"type": "intl_salary_guide", "topic": "Marketing Automation Salary in India", "keyword": "marketing automation salary india", "market": "India", "currency": "INR (express figures in lakhs per annum)", "cities": "Bengaluru, Mumbai, Hyderabad, Gurgaon", "location_slug": "india"},
    # Tier 8: AI × MarTech — the questions practitioners persistently ask and
    # that AI answer engines get asked constantly. Evergreen, high-intent, and
    # each post doubles as LinkedIn material (auto-shared via /blog/feed/).
    {"type": "ai_martech", "topic": "Will AI Replace Marketing Operations?", "keyword": "will ai replace marketing operations", "angle": "An honest assessment of which MOps tasks AI automates (list building, QA, campaign assembly) vs what it can't (strategy, governance, stakeholder management, data judgment) — and how the role is shifting rather than disappearing."},
    {"type": "ai_martech", "topic": "AI Skills Every MarTech Professional Needs", "keyword": "ai skills for martech professionals", "angle": "Concrete, learnable skills: prompt engineering for campaign copy/QA, AI features inside Marketo/HubSpot/Braze/SFMC, CDP + AI activation, AI governance and brand-safety guardrails. Skip the hype; name actual product features."},
    {"type": "ai_martech", "topic": "How AI Is Changing Salesforce Marketing Cloud Work", "keyword": "ai in salesforce marketing cloud", "angle": "Einstein features (send-time optimization, engagement scoring, generative journeys), what SFMC practitioners should learn, and how job requirements are shifting based on what live SFMC postings now ask for."},
    {"type": "ai_martech", "topic": "AI in Marketing Automation: What's Real and What's Hype", "keyword": "ai marketing automation", "angle": "A practitioner's cut-through: AI features that deliver today (subject-line generation, predictive scoring, content variants) vs vaporware. Include how to evaluate vendor AI claims."},
    {"type": "ai_martech", "topic": "How to Future-Proof Your Marketing Ops Career in the AI Era", "keyword": "future proof marketing operations career ai", "angle": "Career strategy: move up the stack toward architecture/strategy/governance, own the data layer, become the person who deploys AI rather than the person it replaces. Practical 12-month plan."},
    {"type": "ai_martech", "topic": "AI Prompt Engineering for Marketing Operations", "keyword": "prompt engineering marketing operations", "angle": "Hands-on: reusable prompt patterns for campaign QA, UTM audits, email copy variants, data-hygiene checks, and JD screening — with concrete example prompts practitioners can copy."},
]

CATEGORY_MAP = {
    "company_careers": "Career Advice",
    "role_guide": "Career Advice",
    "salary_guide": "Salary Guides",
    "intl_salary_guide": "Salary Guides",
    "location_guide": "Career Advice",
    "ai_martech": "AI in MarTech",
    "data_piece": "AI in MarTech",
}


def _live_data_digest():
    """Compute a compact, REAL stats digest from live listings for data_piece
    posts. The prompt forbids any number not present here, so nothing in a
    'your data' article can be fabricated (site rule: every number is real)."""
    from django.db.models import Count, Q as _Q
    from jobs.models import Job, Tool

    live = Job.objects.filter(is_active=True, screening_status='approved')
    total = live.count()
    if not total:
        return None
    remote = live.filter(work_arrangement='remote').count()

    top_tools = list(
        Tool.objects.annotate(
            n=Count('jobs', filter=_Q(jobs__is_active=True, jobs__screening_status='approved'))
        ).filter(n__gt=0).order_by('-n')[:10].values_list('name', 'n')
    )

    # Word-boundary matching in Python (icontains substrings over-count:
    # ' ai.' matches "Dubai." etc.). These figures get PUBLISHED as real
    # stats, so precision beats query elegance. ~300 rows — cheap.
    import re as _re
    ai_pat = _re.compile(r'\b(ai|genai|artificial intelligence|generative ai|machine learning|llms?)\b', _re.IGNORECASE)
    ai_mentions = sum(
        1 for d in live.values_list('description', flat=True) if d and ai_pat.search(d)
    )

    senior_q = (_Q(title__icontains='senior') | _Q(title__icontains='lead')
                | _Q(title__icontains='staff') | _Q(title__icontains='principal')
                | _Q(title__icontains='director') | _Q(title__icontains='head of'))
    senior = live.filter(senior_q)
    senior_count = senior.count()
    senior_tools = list(
        Tool.objects.annotate(
            n=Count('jobs', filter=_Q(jobs__in=senior))
        ).filter(n__gt=0).order_by('-n')[:5].values_list('name', 'n')
    )

    with_salary = live.exclude(salary_range__isnull=True).exclude(salary_range='').count()
    by_function = list(live.values('function').annotate(n=Count('id')).order_by('-n').values_list('function', 'n'))

    lines = [
        f"- Total live MarTech job listings analyzed: {total}",
        f"- Fully remote: {remote} ({round(remote * 100 / total)}%)",
        f"- Listings whose description mentions AI / machine learning: {ai_mentions} ({round(ai_mentions * 100 / total)}%)",
        f"- Senior-level listings (Senior/Lead/Staff/Principal/Director titles): {senior_count} ({round(senior_count * 100 / total)}%)",
        f"- Listings publishing a salary range: {with_salary} ({round(with_salary * 100 / total)}%)",
        "- Platform demand (live listings naming each): " + ", ".join(f"{n} ({c})" for n, c in top_tools),
        "- Platforms in SENIOR listings: " + ", ".join(f"{n} ({c})" for n, c in senior_tools),
        "- Listings by function: " + ", ".join(f"{f} ({c})" for f, c in by_function),
    ]
    return "\n".join(lines)


# Appended to every generated-post prompt. AI answer engines (ChatGPT search,
# Perplexity, Google AI Overviews, Claude) extract and cite content that leads
# with the answer, uses question-form headings, and includes concrete stats —
# cited/statistic-bearing content is ~30-40% more visible in AI search (GEO,
# Aggarwal et al., 2023). GA4 already shows ~12% of our traffic arriving from
# AI assistants, so every post is written to be quotable by them.
_AEO_SUFFIX = """

ANSWER-ENGINE OPTIMIZATION (mandatory — this content must be quotable by AI search engines like ChatGPT, Perplexity, and Google AI Overviews):
- The FIRST paragraph must directly answer the core question of the piece in 2-3 self-contained sentences (a reader — or an AI — should get the complete short answer without reading further).
- Phrase most <h2> headings as natural-language questions people actually ask (e.g. "How much does a Marketing Operations Manager make in London?").
- Immediately under each question heading, give the direct answer in the first sentence, THEN elaborate.
- Include concrete numbers wherever honest and defensible (salary ranges, tool counts, timelines). Never fabricate statistics — use widely-reported industry ranges and hedge appropriately ("typically", "commonly reported").
- End with an <h2>Frequently Asked Questions</h2> section containing 3-5 <h3> question/answer pairs, each answer 2-4 sentences and fully self-contained.
- Write in a natural, conversational register — the way an expert would answer a colleague's question — while staying technically precise."""


def _build_prompt(topic: dict) -> str:
    base = _build_prompt_base(topic)
    return base + _AEO_SUFFIX


def _build_prompt_base(topic: dict) -> str:
    t = topic["type"]
    if t == "company_careers":
        company = topic["company"]
        keyword = topic["keyword"]
        tool_slug = topic["tool_slug"]
        return f"""You are a senior content writer for MarTechJobs.io, the niche job board for Marketing Technology professionals.

Write a comprehensive, SEO-optimized careers guide targeting the keyword: "{keyword}"

Target company: {company}
Target keyword: {keyword}

Requirements:
- H1: Use the exact keyword phrase naturally (e.g. "HubSpot Careers: Roles, Hiring Process & How to Land a Job")
- Structure:
  1. Intro (why {company} is a top MarTech employer)
  2. Types of MarTech/Marketing Ops roles at {company} (list 4-6 real role types)
  3. What skills {company} looks for (tools, certs, experience)
  4. The hiring process at {company} (typical stages)
  5. Salary ranges for {company} MarTech roles
  6. CTA: "Browse open {company} jobs on MarTechJobs" linking to https://martechjobs.io/jobs/{tool_slug}/
- Tone: Direct, credible, written for MarTech practitioners (not generic career advice)
- Length: 800-1200 words
- Output: Clean HTML using <h2>, <h3>, <p>, <ul>, <li>, <strong> only. No markdown. No code fences.
- The CTA link MUST be: <a href="https://martechjobs.io/jobs/{tool_slug}/">Browse open {company} jobs on MarTechJobs →</a>

Output strict JSON:
{{"title": "...", "excerpt": "...", "content": "...", "meta_description": "...", "read_time": "..."}}"""

    elif t == "role_guide":
        topic_name = topic["topic"]
        keyword = topic["keyword"]
        return f"""You are a senior content writer for MarTechJobs.io.

Write a comprehensive role guide targeting: "{keyword}"
Role: {topic_name}

Structure:
1. What does a {topic_name} do?
2. Required skills and tools
3. Career path and progression
4. Salary expectations
5. How to get hired (CTA to MarTechJobs search)

Output strict JSON with title, excerpt, content (clean HTML), meta_description, read_time."""

    elif t == "salary_guide":
        topic_name = topic["topic"]
        keyword = topic["keyword"]
        return f"""You are a senior content writer for MarTechJobs.io.

Write a data-driven salary guide targeting: "{keyword}"
Topic: {topic_name}

Structure:
1. Average salary range (be specific with ranges like $85,000–$130,000)
2. Salary by experience level (junior/mid/senior)
3. Salary by city/location
4. Factors that affect salary
5. How to negotiate
6. CTA to browse related jobs on MarTechJobs

Output strict JSON with title, excerpt, content (clean HTML), meta_description, read_time."""

    elif t == "intl_salary_guide":
        topic_name = topic["topic"]
        keyword = topic["keyword"]
        market = topic["market"]
        currency = topic["currency"]
        cities = topic["cities"]
        location_slug = topic["location_slug"]
        return f"""You are a senior content writer for MarTechJobs.io, the niche job board for Marketing Technology professionals.

Write a data-driven salary guide for the {market} market targeting: "{keyword}"
Topic: {topic_name}

CRITICAL — currency and format: {currency}. Use the salary notation local job
seekers in {market} actually use and search for. Do NOT quote US dollar figures
except for a single brief global comparison.

Structure:
1. Direct answer first: the typical salary range for this role in {market} today
2. Salary by experience level (0-2 yrs / 3-5 yrs / 6+ yrs)
3. Salary by city ({cities}) — note which cities pay a premium and why
4. Product companies vs services/consulting firms (GCCs, SIs like Accenture/Deloitte/Infosys) — how compensation differs, since much of {market}'s MarTech hiring is services-side
5. Skills and certifications that move the number most
6. How to negotiate in the {market} market
7. CTA: <a href="https://martechjobs.io/{location_slug}/jobs/">Browse live MarTech jobs in {market} on MarTechJobs →</a>

Use widely-reported {market} salary ranges and hedge honestly ("commonly reported", "typically") — never invent precise statistics.
Tone: direct, technically credible, written for {market}-based practitioners.
Length: 900-1300 words.
Output: Clean HTML using <h2>, <h3>, <p>, <ul>, <li>, <strong> only.

Output strict JSON with title, excerpt, content (clean HTML), meta_description, read_time."""

    elif t == "data_piece":
        topic_name = topic["topic"]
        keyword = topic["keyword"]
        angle = topic["angle"]
        data = topic.get("data") or "(no live data available)"
        return f"""You are the founder of MarTechJobs.io writing a data-driven analysis piece from the job board's own live listings.

Write an original analysis targeting: "{keyword}"
Topic: {topic_name}

Editorial angle (follow closely): {angle}

LIVE DATA FROM OUR LISTINGS (computed today — this is the article's spine):
{data}

HARD DATA RULES:
- You may cite ONLY the numbers in the LIVE DATA block above. Do not invent, extrapolate to, or "estimate" any other statistic about our listings.
- Attribute the data naturally: "across the {'{'}total{'}'} live listings on MarTechJobs" / "our live listings show…". Use the actual total from the data block.
- General industry context is allowed but must be hedged ("widely reported", "industry surveys suggest") and clearly separate from OUR data.
- Voice: first-person founder field notes — direct, technically credible, zero recruiter fluff.
- Where natural, link to <a href="https://martechjobs.io/martech-job-market-statistics/">our live market statistics page</a> and CTA to <a href="https://martechjobs.io/jobs/">live MarTech jobs</a>.
- Length: 900-1300 words.
- Output: Clean HTML using <h2>, <h3>, <p>, <ul>, <li>, <strong> only.

Output strict JSON with title, excerpt, content (clean HTML), meta_description, read_time."""

    elif t == "ai_martech":
        topic_name = topic["topic"]
        keyword = topic["keyword"]
        angle = topic["angle"]
        return f"""You are a senior MarTech practitioner writing for MarTechJobs.io, the niche job board for Marketing Technology professionals.

Write a credible, practitioner-grade article targeting: "{keyword}"
Topic: {topic_name}

Editorial angle (follow this closely): {angle}

Hard rules:
- NO breathless AI hype and NO doom. The reader is a working MOps/MarTech professional who wants the honest, useful answer.
- Name REAL products and features where relevant (Marketo, HubSpot, Braze, SFMC/Einstein, Segment, Adobe Experience Platform) — never invent product capabilities.
- Include practical, do-this-tomorrow takeaways, not abstractions.
- Where the topic touches hiring/careers, tie it to what employers actually list in job requirements, and CTA to <a href="https://martechjobs.io/jobs/">live MarTech jobs on MarTechJobs</a>.
- Length: 900-1300 words.
- Output: Clean HTML using <h2>, <h3>, <p>, <ul>, <li>, <strong> only.

Output strict JSON with title, excerpt, content (clean HTML), meta_description, read_time."""

    elif t == "location_guide":
        topic_name = topic["topic"]
        keyword = topic["keyword"]
        location_name = topic["location_name"]
        location_slug = topic["location_slug"]
        return f"""You are a senior content writer for MarTechJobs.io, the niche job board for Marketing Technology professionals.

Write a comprehensive, SEO-optimized guide targeting the keyword: "{keyword}"

Market: {location_name}

Requirements:
- H1: Use the keyword phrase naturally (e.g. "MarTech Jobs in {location_name}: Roles, Employers & Salaries")
- Structure:
  1. Intro — the state of the MarTech job market in {location_name} (key cities/hubs)
  2. Most in-demand MarTech roles in {location_name} (Marketing Ops, automation, analytics, CDP)
  3. Tools and skills employers in {location_name} hire for
  4. Types of companies hiring (vendors, SaaS, local enterprises) — name realistic examples
  5. Typical salary ranges in {location_name} (use LOCAL currency, be specific)
  6. How to find and land these roles
  7. CTA: "Browse open MarTech jobs in {location_name}" linking to https://martechjobs.io/{location_slug}/jobs/
- Tone: Direct, credible, written for MarTech practitioners — not generic career advice
- Length: 800-1200 words
- Output: Clean HTML using <h2>, <h3>, <p>, <ul>, <li>, <strong> only. No markdown. No code fences.
- The CTA link MUST be: <a href="https://martechjobs.io/{location_slug}/jobs/">Browse open MarTech jobs in {location_name} →</a>

Output strict JSON:
{{"title": "...", "excerpt": "...", "content": "...", "meta_description": "...", "read_time": "..."}}"""

    raise ValueError(f"Unknown topic type: {t}")


def _topic_slug(entry: dict) -> str:
    """Deterministic, keyword-based slug for a queue entry. Used both to detect
    whether a topic was already written and as the published post's slug, so
    detection is exact (no fragile title-substring matching) AND the URL is
    keyword-rich (e.g. /blog/hubspot-careers/)."""
    return slugify(entry["keyword"])


# Slugs owned by non-post routes under /blog/ — a post with one of these slugs
# would be created but unreachable (the section/feed route matches first).
_RESERVED_POST_SLUGS = {"ai-in-martech", "salary-guides", "career-advice", "tech-stacks", "feed"}


def _pick_next_topic() -> Optional[dict]:
    """Return the first TOPIC_QUEUE entry whose keyword-slug doesn't already
    exist as a BlogPost. Exact-slug match avoids false positives from unrelated
    posts that merely mention a company/keyword (e.g. a 'HubSpot vs Marketo'
    post must NOT block the dedicated 'hubspot careers' guide)."""
    existing_slugs = set(BlogPost.objects.values_list("slug", flat=True))
    for entry in TOPIC_QUEUE:
        slug = _topic_slug(entry)
        if slug in _RESERVED_POST_SLUGS:
            continue  # would be shadowed by a section/feed route — skip
        if slug not in existing_slugs:
            return entry
    return None  # All topics covered


class Command(BaseCommand):
    help = 'Generates an SEO-optimized blog post using AI. Runs maximum once per week.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Skip the 7-day throttle and generate a post immediately.',
        )

    def handle(self, *args, **options):
        self.stdout.write("Booting up AI Content Engine...")

        # 1. 7-DAY RULE: Check if we need to post
        # normalize_blog_posts rewrites the author to "MarTechJobs Team", so the
        # throttle must match both spellings or it would never see prior AI posts
        # and would generate one every run.
        if not options.get('force'):
            latest_post = BlogPost.objects.filter(
                author__in=["MarTechJobs AI", "MarTechJobs Team"]
            ).order_by('-published_at').first()

            if latest_post and latest_post.published_at > (timezone.now() - timedelta(days=7)).date():
                self.stdout.write(self.style.SUCCESS("   A recent AI blog post already exists (less than 7 days old). Skipping generation."))
                return

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            self.stdout.write(self.style.ERROR("   Missing OPENAI_API_KEY in environment variables."))
            return

        client = OpenAI(api_key=api_key, timeout=60, max_retries=2)

        # 2. Pick next unwritten topic from the prioritized queue
        selected = _pick_next_topic()
        if selected is None:
            self.stdout.write(self.style.SUCCESS("   All queued topics have been covered. Nothing to generate."))
            return

        label = selected.get("keyword") or selected.get("topic", "")
        self.stdout.write(f"   Drafting article for: '{label}' (type={selected['type']})...")

        # 3. Build type-specific prompt. data_piece articles get a live stats
        # digest computed from the DB NOW, so every number they cite is real.
        if selected["type"] == "data_piece":
            digest = _live_data_digest()
            if not digest:
                self.stdout.write(self.style.WARNING("   No live jobs to analyze — skipping data piece."))
                return
            selected = {**selected, "data": digest}
        prompt = _build_prompt(selected)
        category = CATEGORY_MAP[selected["type"]]

        try:
            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert technical SEO writer. Output only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )

            data = json.loads(completion.choices[0].message.content)

            # 4. Slug = deterministic keyword slug (keyword-rich URL + reliable
            # dedup on the next run). Fall back to a suffix only on collision.
            slug = _topic_slug(selected)
            if BlogPost.objects.filter(slug=slug).exists():
                slug = f"{slug}-{random.randint(100, 9999)}"

            post = BlogPost.objects.create(
                title=data['title'],
                slug=slug,
                excerpt=data['excerpt'],
                content=data['content'],
                meta_title=data['title'][:60],
                meta_description=data['meta_description'],
                author="MarTechJobs AI",
                category=category,
                read_time=data['read_time'],
                is_published=True,
                published_at=timezone.now().date()
            )

            self.stdout.write(self.style.SUCCESS(f"Success! Automated post published: {post.title}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"AI Generation Failed: {e}"))
