from django.contrib import admin
from django.urls import path, include, reverse
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from jobs.sitemaps import JobSitemap, ToolSitemap, SEOLandingSitemap # <--- Added Import

# --- DEFINITIONS ---
sitemaps = {
    'jobs': JobSitemap,
    'tools': ToolSitemap, 
    'seo_landing': SEOLandingSitemap, # <--- Added
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
