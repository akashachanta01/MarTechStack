from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.db.models import Count

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
        # FIX: Ensure we only show tools that have APPROVED jobs.
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
        from .models import Tool, Job
        items = []
        if Job.objects.filter(is_active=True, work_arrangement='remote').exists():
            items.append(('remote', None))
        
        remote_tools = Tool.objects.filter(
            jobs__is_active=True, 
            jobs__work_arrangement='remote'
        ).distinct()
        
        for tool in remote_tools:
            items.append(('remote', tool.slug))
        return items

    def location(self, obj):
        loc_slug, tool_slug = obj
        if tool_slug:
            return reverse('seo_tool_loc', args=[loc_slug, tool_slug])
        else:
            return reverse('seo_loc_only', args=[loc_slug])

class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'monthly'
    protocol = 'https'

    def items(self):
        return ['about', 'for_employers', 'post_job', 'job_list']

    def location(self, item):
        return reverse(item)
