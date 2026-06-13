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
        # EXPOSE ALL TOOLS (Even empty ones, to catch leads)
        return Tool.objects.all().order_by('name')

    def location(self, obj):
        return reverse('tool_detail', args=[obj.slug])

class SEOLandingSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6
    protocol = 'https'

    def items(self):
        from .models import Tool
        
        seo_pages = set()
        
        # 1. Base Remote Pages for ALL tools
        seo_pages.add(('remote', '')) 
        for tool in Tool.objects.all():
            if tool.slug:
                seo_pages.add(('remote', tool.slug))

        # 2. Hardcode Top Hubs to force indexing of combinations
        top_hubs = ["new-york", "san-francisco", "austin", "chicago", "london", "texas", "california"]
        
        for hub in top_hubs:
            seo_pages.add((hub, ''))
            # Limit to top 20 tools per city to avoid blowing up the sitemap size instantly
            for tool in Tool.objects.all()[:20]: 
                if tool.slug:
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
