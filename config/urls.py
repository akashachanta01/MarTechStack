from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse

# Import your Sitemap logic
from jobs.sitemaps import JobSitemap, ToolSitemap, SEOLandingSitemap, StaticViewSitemap, BlogSitemap

# --- 1. DEFINE SITEMAPS ---
# This tells Django (and Google) how to map your content
sitemaps = {
    'jobs': JobSitemap,
    'tools': ToolSitemap,
    'seo_landing': SEOLandingSitemap,
    'static': StaticViewSitemap,
    'blog': BlogSitemap,  # <-- This adds your new blog posts to the sitemap
}

# --- 2. ROBOTS.TXT VIEW ---
# This serves the instructions for Googlebot
def robots_txt(request):
    content = """User-agent: *
Disallow: /admin/
Disallow: /staff/
Disallow: /webhook/
Disallow: /post-job/success/

Sitemap: https://martechjobs.io/sitemap.xml
"""
    return HttpResponse(content, content_type="text/plain")

urlpatterns = [
    # Admin & Apps
    path('admin/', admin.site.urls),
    path('', include('jobs.urls')),  # Delegates normal pages to your jobs app

    # SEO Paths
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt),
]

# Static media serving for debug mode (Local development)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
