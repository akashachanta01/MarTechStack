import os
import json
import random
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
]

CATEGORY_MAP = {
    "company_careers": "Career Advice",
    "role_guide": "Career Advice",
    "salary_guide": "Salary Guides",
}


def _build_prompt(topic: dict) -> str:
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

    raise ValueError(f"Unknown topic type: {t}")


def _topic_slug(entry: dict) -> str:
    """Deterministic, keyword-based slug for a queue entry. Used both to detect
    whether a topic was already written and as the published post's slug, so
    detection is exact (no fragile title-substring matching) AND the URL is
    keyword-rich (e.g. /blog/hubspot-careers/)."""
    return slugify(entry["keyword"])


def _pick_next_topic() -> dict | None:
    """Return the first TOPIC_QUEUE entry whose keyword-slug doesn't already
    exist as a BlogPost. Exact-slug match avoids false positives from unrelated
    posts that merely mention a company/keyword (e.g. a 'HubSpot vs Marketo'
    post must NOT block the dedicated 'hubspot careers' guide)."""
    existing_slugs = set(BlogPost.objects.values_list("slug", flat=True))
    for entry in TOPIC_QUEUE:
        if _topic_slug(entry) not in existing_slugs:
            return entry
    return None  # All topics covered


class Command(BaseCommand):
    help = 'Generates an SEO-optimized blog post using AI. Runs maximum once per week.'

    def handle(self, *args, **options):
        self.stdout.write("Booting up AI Content Engine...")

        # 1. 7-DAY RULE: Check if we need to post
        latest_post = BlogPost.objects.filter(author="MarTechJobs AI").order_by('-published_at').first()

        if latest_post and latest_post.published_at >= (timezone.now() - timedelta(days=6)).date():
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

        # 3. Build type-specific prompt
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
