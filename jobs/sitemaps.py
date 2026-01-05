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
        # Only show tools that have APPROVED jobs.
        return Tool.objects.filter(
            jobs__is_active=True, 
            jobs__screening_status='approved'
        ).distinct()

    def location(self, obj):
        return reverse('tool_detail', args=[obj.slug])

class SEOLandingSitemap(Sitemap):
    """
    THE GROWTH ENGINE:
    Dynamically generates thousands of "Location + Tool" combination pages
    based on the actual jobs in your database.
    """
    changefreq = "weekly"
    priority = 0.6
    protocol = 'https'

    def items(self):
        from .models import Job
        
        # We use a Set to automatically remove duplicates
        seo_pages = set()
        
        # Fetch all active jobs to analyze their locations and tools
        active_jobs = Job.objects.filter(is_active=True, screening_status='approved').prefetch_related('tools')
        
        for job in active_jobs:
            # --- 1. HANDLE REMOTE (Virtual Location) ---
            if job.work_arrangement == 'remote':
                # Add /remote/jobs/
                seo_pages.add(('remote', None))
                # Add /remote/tool-name-jobs/
                for tool in job.tools.all():
                    seo_pages.add(('remote', tool.slug))

            # --- 2. HANDLE PHYSICAL LOCATIONS ---
            if job.location:
                # Heuristic: "New York, NY, USA" -> "New York"
                # We split by comma and take the first part to get the City name.
                raw_city = job.location.split(',')[0].strip()
                city_slug = slugify(raw_city)

                if city_slug and city_slug != 'remote':
                    # Add /city/jobs/
                    seo_pages.add((city_slug, None))
                    # Add /city/tool-name-jobs/
                    for tool in job.tools.all():
                        seo_pages.add((city_slug, tool.slug))
        
        # Return sorted list for consistent sitemap ordering
        return sorted(list(seo_pages))

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
