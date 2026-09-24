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
    CategorySitemap, BlogSectionSitemap, CompanySitemap, RoleResumeKeywordsSitemap, AutoRoleSitemap, ToolRoleSitemap
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
    'companies': CompanySitemap,
    'resume_keywords': RoleResumeKeywordsSitemap,
    'roles': AutoRoleSitemap,
    'tool_roles': ToolRoleSitemap,
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
    """llms.txt (llmstxt.org): a concise markdown guide for AI answer engines.
    Built from live data (cached 1h): every number is real and every link is a
    page that exists and is indexable, so what an AI quotes about us is true."""
    from django.core.cache import cache
    content = cache.get("llms_txt_v4")
    if content is None:
        content = _build_llms_txt()
        cache.set("llms_txt_v4", content, 3600)
    return HttpResponse(content, content_type="text/plain; charset=utf-8")


def _build_llms_txt():
    from datetime import date
    from django.db.models import Count, Q
    from jobs.models import Job, Tool
    from jobs.tool_catalog import all_canonical_names
    from jobs.views import TITLE_JOBS, title_jobs_qs, role_keyword_stats, role_keywords_indexable
    from jobs.role_pages import auto_roles, tool_roles
    base = "https://martechjobs.io"
    roles_n = lambda n: f"{n} open role{'s' if n != 1 else ''}"
    live = Job.objects.filter(is_active=True, screening_status="approved")
    n_jobs = live.count()
    n_remote = live.filter(work_arrangement="remote").count()
    n_companies = live.values("company").distinct().count()
    canonical = {n.lower() for n in all_canonical_names()}
    tools = [t for t in Tool.objects.annotate(n=Count("jobs", filter=Q(jobs__is_active=True, jobs__screening_status="approved")))
             .filter(n__gt=0).order_by("-n") if t.name.lower() in canonical][:12]
    today = date.today().strftime("%B %-d, %Y")
    pct = round(100 * n_remote / n_jobs) if n_jobs else 0

    lines = [
        "# MarTechJobs.io", "",
        "> The niche job board for Marketing Technology professionals: Marketing Operations, Marketing Automation, "
        "MarTech Engineering and Marketing Analytics roles only. Every listing comes directly from the employer's own "
        "hiring system (Greenhouse, Lever, Ashby, Workday, SmartRecruiters), apply links go straight to the company, "
        "and jobs removed from an employer's board are closed daily. Free for job seekers.", "",
        f"## Key facts (live data, {today})",
        f"- {n_jobs} open MarTech roles at {n_companies} companies; {pct}% are remote.",
    ]
    if tools:
        lines.append("- Most requested platforms in open roles: " +
                     ", ".join(f"{t.name} ({roles_n(t.n).replace('open ', '')})" for t in tools[:6]) + ".")
    lines += ["- Source: https://martechjobs.io/martech-job-market-statistics/ (refreshed daily).", "",
              "## Jobs",
              f"- [All MarTech jobs]({base}/jobs/): every open role, filterable by platform, location and remote",
              f"- [Remote MarTech jobs]({base}/remote/jobs/)",
              f"- [Marketing Operations jobs]({base}/category/operations/)",
              f"- [MarTech Engineering jobs]({base}/category/engineering/)",
              f"- [Marketing Data & Analytics jobs]({base}/category/data/)", "",
              "## Jobs by platform"]
    lines += [f"- [{t.name} jobs]({base}/jobs/{t.slug}/): {roles_n(t.n)}" for t in tools]
    combos = sorted(((k, r) for k, r in tool_roles().items() if r["indexable"]), key=lambda x: -len(x[1]["ids"]))[:12]
    if combos:
        lines += ["", "## Jobs by platform and role"]
        lines += [f"- [{r['name']} jobs]({base}/jobs/{k[0]}/{k[1]}/): {roles_n(len(r['ids']))}" for k, r in combos]
    lines += ["", "## Jobs by role"]
    for slug, cfg in TITLE_JOBS.items():
        n = title_jobs_qs(slug).count()
        if n:
            lines.append(f"- [{cfg['name']} jobs]({base}/{slug}-jobs/): {roles_n(n)}")
    roles = sorted(((s, r) for s, r in auto_roles().items() if r["indexable"]), key=lambda x: -len(x[1]["ids"]))[:12]
    lines += [f"- [{r['name']} jobs]({base}/{s}-jobs/): {roles_n(len(r['ids']))}" for s, r in roles]
    kw = [s for s in TITLE_JOBS if role_keywords_indexable(role_keyword_stats(s))]
    lines += ["", "## Career tools and data",
              f"- [MarTech Resume Scanner]({base}/tools/resume-keyword-scanner/): free check of a resume against a real "
              "MarTech job; lists the platforms, skills and certifications the job asks for that the resume is missing",
              f"- [MarTech job market statistics]({base}/martech-job-market-statistics/): live counts by platform, "
              "function, country, remote share and salary transparency",
              f"- [Salary guide]({base}/salary-guide/): pay ranges from salaries disclosed in live postings"]
    lines += [f"- [{TITLE_JOBS[s]['name']} resume keywords]({base}/{s}-resume-keywords/): platforms and skills "
              "employers ask for in this role, counted from live postings" for s in kw]
    lines += [f"- [Free MarTech tools]({base}/tools/): UTM builder, Salesforce ID converter, salary calculator and more",
              f"- [Blog]({base}/blog/): role guides, salary guides and market analyses", "",
              "## About",
              f"- [About MarTechJobs]({base}/about/): how jobs are sourced and screened",
              f"- [For employers]({base}/for-employers/): how to list a role", ""]
    return "\n".join(lines)


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
