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
        return Tool.objects.filter(
            jobs__is_active=True, 
            jobs__screening_status='approved'
        ).distinct()

    def location(self, obj):
        return reverse('tool_detail', args=[obj.slug])

class SEOLandingSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6
    protocol = 'https'

    def items(self):
        from .models import Job
        
        seo_pages = set()
        active_jobs = Job.objects.filter(is_active=True, screening_status='approved').prefetch_related('tools')
        
        for job in active_jobs:
            try:
                if job.work_arrangement == 'remote':
                    seo_pages.add(('remote', '')) 
                    for tool in job.tools.all():
                        if tool.slug:
                            seo_pages.add(('remote', tool.slug))

                if job.location:
                    raw_city = job.location.split(',')[0].strip()
                    city_slug = slugify(raw_city)

                    if city_slug and city_slug != 'remote':
                        seo_pages.add((city_slug, ''))
                        for tool in job.tools.all():
                            if tool.slug:
                                seo_pages.add((city_slug, tool.slug))
            except Exception:
                continue
        
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

# --- NEW: STATIC TOOLS SITEMAP ---
# This ensures your calculators and generators are found by Google.
class ToolsStaticSitemap(Sitemap):
    priority = 0.9  # High priority because these are "Link Magnets"
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
            'resume_scanner'
        ]

    def location(self, item):
        return reverse(item)

class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'monthly'
    protocol = 'https'

    def items(self):
        return ['about', 'for_employers', 'post_job', 'job_list', 'blog_list']

    def location(self, item):
        return reverse(item)
