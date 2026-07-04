from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse

# Import your Sitemap logic
from jobs.sitemaps import (
    JobSitemap, ToolSitemap, SEOLandingSitemap,
    StaticViewSitemap, BlogSitemap, ToolsStaticSitemap, TitleJobsSitemap,
    InterviewGuideSitemap, RoleSalarySitemap, CertificationGuideSitemap,
    CategorySitemap, BlogSectionSitemap
)

# --- 1. DEFINE SITEMAPS ---
sitemaps = {
    'jobs': JobSitemap,
    'tools': ToolSitemap,
    'tools_static': ToolsStaticSitemap,
    'seo_landing': SEOLandingSitemap,
    'titles': TitleJobsSitemap,
    'interview_guides': InterviewGuideSitemap,
    'role_salaries': RoleSalarySitemap,
    'cert_guides': CertificationGuideSitemap,
    'categories': CategorySitemap,
    'static': StaticViewSitemap,
    'blog': BlogSitemap,
    'blog_sections': BlogSectionSitemap,
}

# --- 2. ROBOTS.TXT VIEW ---
def robots_txt(request):
    # AI/answer-engine crawlers are explicitly WELCOMED (AEO): being crawlable
    # by GPTBot/OAI-SearchBot (ChatGPT), PerplexityBot, ClaudeBot, and
    # Google-Extended (Gemini/AI Overviews) is how the site gets cited in AI
    # answers — already ~12% of our traffic. Explicit sections document intent
    # and guard against a future blanket block accidentally cutting them off.
    content = """User-agent: *
Disallow: /admin/
Disallow: /staff/
Disallow: /webhook/
Disallow: /post-job/success/
Disallow: /*?q=
Disallow: /*?l=
Disallow: /*&q=
Disallow: /*&l=
Disallow: /*?sort=
Disallow: /*&sort=

# --- AI / answer-engine crawlers: explicitly allowed ---
User-agent: GPTBot
Disallow: /admin/
Allow: /

User-agent: OAI-SearchBot
Disallow: /admin/
Allow: /

User-agent: ChatGPT-User
Disallow: /admin/
Allow: /

User-agent: PerplexityBot
Disallow: /admin/
Allow: /

User-agent: ClaudeBot
Disallow: /admin/
Allow: /

User-agent: Claude-Web
Disallow: /admin/
Allow: /

User-agent: Google-Extended
Disallow: /admin/
Allow: /

Sitemap: https://martechjobs.io/sitemap.xml
"""
    return HttpResponse(content, content_type="text/plain")


# --- 2b. LLMS.TXT VIEW (AEO) ---
def llms_txt(request):
    """llms.txt (llmstxt.org): a concise, markdown site guide for AI answer
    engines. Live counts are pulled from the DB (cached 1h) so the numbers an
    AI quotes about us are always real — per the site rule that every number
    shown must be true."""
    from django.core.cache import cache
    content = cache.get("llms_txt_v3")
    if content is None:
        try:
            from jobs.models import Job, Tool
            live = Job.objects.filter(is_active=True, screening_status="approved")
            n_jobs = live.count()
            n_remote = live.filter(work_arrangement="remote").count()
            n_tools = Tool.objects.filter(
                jobs__is_active=True, jobs__screening_status="approved"
            ).distinct().count()
            stats_line = (
                f"Currently listing {n_jobs} live roles ({n_remote} remote) "
                f"across {n_tools}+ MarTech platforms, refreshed daily."
            )
        except Exception:
            stats_line = "Job listings are refreshed daily from company hiring systems."
        content = f"""# MarTechJobs.io

> The niche job board for Marketing Technology professionals: Marketing Operations, Marketing Automation, MarTech Engineering, and Marketing Analytics roles only. Every listing is pulled directly from the employer's own hiring system (Greenhouse, Lever, Ashby, Workday, SmartRecruiters), so apply links go straight to the company — no recruiters or reposts. {stats_line} Free for job seekers.

## Jobs
- [All live MarTech jobs](https://martechjobs.io/jobs/): every open role, filterable by tool, location, and work arrangement
- [Remote MarTech jobs](https://martechjobs.io/remote/jobs/): remote-only roles
- [Marketing Operations jobs](https://martechjobs.io/marketing-operations-jobs/): the core MOps discipline
- [Salesforce jobs](https://martechjobs.io/jobs/salesforce/) and [Marketo jobs](https://martechjobs.io/jobs/marketo/): roles by platform

## Jobs by market
- [United States](https://martechjobs.io/jobs/), [India](https://martechjobs.io/india/jobs/), [United Kingdom](https://martechjobs.io/united-kingdom/jobs/), [Singapore](https://martechjobs.io/singapore/jobs/), [Germany](https://martechjobs.io/germany/jobs/), [Canada](https://martechjobs.io/canada/jobs/)

## Guides & data
- [MarTech job market statistics](https://martechjobs.io/martech-job-market-statistics/): live counts by platform, function, country, remote share, and salary transparency — refreshed daily, citable
- [AI in MarTech](https://martechjobs.io/blog/ai-in-martech/): practitioner-grade guides on how AI is changing Marketing Operations work, skills, and careers
- [Blog](https://martechjobs.io/blog/): salary guides, role guides, and market analyses for MarTech careers
- [Salary guide](https://martechjobs.io/salary-guide/): compensation data for Marketing Ops and MarTech roles
- [Free tools](https://martechjobs.io/tools/): salary calculator, JD generator, interview-question generator, and other MarTech utilities

## About
- [About MarTechJobs](https://martechjobs.io/about/): who runs the site and how jobs are sourced and screened
- [For employers](https://martechjobs.io/for-employers/): how to list roles
"""
        cache.set("llms_txt_v3", content, 3600)
    return HttpResponse(content, content_type="text/plain; charset=utf-8")


# --- 2c. INDEXNOW KEY FILE ---
def indexnow_key(request):
    """Serves the IndexNow verification key (INDEXNOW_KEY env var). The
    ping_indexnow command points Bing/Seznam/Yandex here via keyLocation, which
    proves we own the host. ChatGPT search is built on Bing's index, so fast
    Bing indexing = fast visibility in ChatGPT answers. 404s if unconfigured."""
    import os
    key = os.environ.get("INDEXNOW_KEY", "").strip()
    if not key:
        from django.http import Http404
        raise Http404
    return HttpResponse(key, content_type="text/plain")



urlpatterns = [
    # Admin & Apps
    path('admin/', admin.site.urls),
    path('tools/', include('tools.urls')),
    path('accounts/', include('accounts.urls')),
    path('', include('jobs.urls')),

    # SEO Paths
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt),
    path('llms.txt', llms_txt),
    path('indexnow.txt', indexnow_key),
]

# Static media serving for debug mode (Local development)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
