from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils.text import slugify

class JobSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8
    protocol = 'https'

    def items(self):
        from .models import Job
        return Job.objects.filter(is_active=True, screening_status='approved')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('job_detail', args=[obj.id, obj.slug])

class ToolSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7
    protocol = 'https'
    
    def items(self):
        from .models import Tool
        from .tool_catalog import all_canonical_names
        canonical = {n.lower() for n in all_canonical_names()}
        # Only CANONICAL tools with at least one live job. Excludes junk tools
        # (ssf, paid-media-data, crm, …) and empty thin pages.
        tools = (
            Tool.objects.filter(jobs__is_active=True, jobs__screening_status='approved')
            .distinct().order_by('name')
        )
        return [t for t in tools if (t.name or '').lower() in canonical]

    def location(self, obj):
        return reverse('tool_detail', args=[obj.slug])

class SEOLandingSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6
    protocol = 'https'

    def items(self):
        from .models import Tool
        from .tool_catalog import all_canonical_names
        canonical = {n.lower() for n in all_canonical_names()}
        # Only canonical tools with live jobs go into location combos — no junk.
        canonical_tools = [
            t for t in Tool.objects.filter(jobs__is_active=True, jobs__screening_status='approved').distinct()
            if t.slug and (t.name or '').lower() in canonical
        ]

        seo_pages = set()

        # 1. Base remote pages for canonical tools
        seo_pages.add(('remote', ''))
        for tool in canonical_tools:
            seo_pages.add(('remote', tool.slug))

        # 2. Curated hubs × canonical tools (no arbitrary cities)
        top_hubs = ["new-york", "san-francisco", "austin", "chicago", "london", "texas", "california"]

        for hub in top_hubs:
            seo_pages.add((hub, ''))
            for tool in canonical_tools[:20]:
                seo_pages.add((hub, tool.slug))

        return sorted(list(seo_pages))

    def location(self, obj):
        loc_slug, tool_slug = obj
        if tool_slug:
            return reverse('seo_tool_loc', args=[loc_slug, tool_slug])
        else:
            return reverse('seo_loc_only', args=[loc_slug])

class BlogSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = 'https'

    def items(self):
        from .models import BlogPost
        return BlogPost.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('post_detail', args=[obj.slug])

class RoleSalarySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7
    protocol = 'https'

    def items(self):
        from jobs.views import TITLE_JOBS
        return list(TITLE_JOBS.keys())

    def location(self, slug):
        return f"/{slug}-salary/"


class InterviewGuideSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = 'https'

    def items(self):
        from .models import InterviewGuide
        # Only emit guides that are actually indexable (>= 5 questions), matching
        # the noindex gate in tool_interview — no point sitemapping noindex pages.
        guides = InterviewGuide.objects.filter(is_published=True).select_related('tool').order_by('slug')
        return [g for g in guides if g.question_count() >= 5]

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('tool_interview', args=[obj.tool.slug])


# --- STATIC TOOLS SITEMAP (UPDATED) ---
class ToolsStaticSitemap(Sitemap):
    priority = 0.9  # Highest priority assets
    changefreq = 'monthly'
    protocol = 'https'

    def items(self):
        return [
            'jd_generator', 
            'salary_calculator', 
            'interview_generator', 
            'signature_generator', 
            'sf_id_converter',
            'qr_generator',
            'utm_builder',
            'sql_generator',
            'consultant_calculator',
            'resume_scanner',
            'roas_calculator',      
            'subject_line_tester',  
        ]

    def location(self, item):
        return reverse(item)

# --- STATIC VIEWS SITEMAP (UPDATED) ---
class StaticViewSitemap(Sitemap):
    priority = 0.6
    changefreq = 'monthly'
    protocol = 'https'

    def items(self):
        return [
            'about',
            'for_employers',
            'post_job',
            'job_list',
            'blog_list',
            'salary_guide',
            'directory',
            'company_list',
            'all_jobs',
            'privacy',
            'terms',
        ]

    def location(self, item):
        return reverse(item)


class TitleJobsSitemap(Sitemap):
    """Programmatic job-title pages (/<title>-jobs/)."""
    priority = 0.8
    changefreq = 'daily'
    protocol = 'https'

    def items(self):
        from jobs.views import TITLE_JOBS
        return list(TITLE_JOBS.keys())

    def location(self, slug):
        return f'/{slug}-jobs/'


class InterviewGuideSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = 'https'

    def items(self):
        from .models import InterviewGuide
        # Only emit guides that are actually indexable (>= 5 questions), matching
        # the noindex gate in tool_interview — no point sitemapping noindex pages.
        guides = InterviewGuide.objects.filter(is_published=True).select_related('tool').order_by('slug')
        return [g for g in guides if g.question_count() >= 5]

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('tool_interview', args=[obj.tool.slug])


class CategorySitemap(Sitemap):
    """The three top-level category hubs (/category/<slug>/). They're linked in
    the nav and footer but were missing from the sitemap, so Google had no
    explicit recrawl signal for them."""
    changefreq = "daily"
    priority = 0.8
    protocol = 'https'

    def items(self):
        from jobs.views import CATEGORY_CONFIG
        return list(CATEGORY_CONFIG.keys())

    def location(self, slug):
        return reverse('category_detail', args=[slug])


class CertificationGuideSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = 'https'

    def items(self):
        from .models import CertificationGuide
        # Only emit guides with a study path (indexable), matching the noindex
        # gate in tool_certification — don't sitemap pages we noindex.
        guides = CertificationGuide.objects.filter(is_published=True).select_related('tool').order_by('slug')
        return [g for g in guides if g.study_path]

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('tool_certification', args=[obj.tool.slug])
