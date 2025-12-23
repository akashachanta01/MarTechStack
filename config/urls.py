from django.contrib import admin
from django.urls import path, include, reverse
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse

# --- 1. JOB SITEMAP ---
class JobSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8
    protocol = 'https'

    def items(self):
        from jobs.models import Job
        return Job.objects.filter(is_active=True, screening_status='approved')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('job_detail', args=[obj.id, obj.slug])

# --- 2. TOOL SITEMAP (New Topic Clusters) ---
class ToolSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6
    protocol = 'https'

    def items(self):
        from jobs.models import Tool
        # Only list tools that actually have jobs
        return Tool.objects.filter(jobs__is_active=True).distinct()

    def location(self, obj):
        return reverse('tool_detail', args=[obj.slug])

# --- DEFINITIONS ---
sitemaps = {
    'jobs': JobSitemap,
    'tools': ToolSitemap, 
}

# --- ROBOTS.TXT ---
def robots_txt(request):
    content = f"""User-agent: *
Disallow: /admin/
Disallow: /staff/

Sitemap: {settings.DOMAIN_URL}/sitemap.xml
"""
    return HttpResponse(content, content_type="text/plain")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('jobs.urls')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
