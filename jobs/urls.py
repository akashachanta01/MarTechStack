from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse

# Import the Sitemap class
from jobs.sitemaps import JobSitemap

# Define the dictionary of sitemaps
sitemaps = {
    'jobs': JobSitemap,
}

# Simple Robots.txt view
def robots_txt(request):
    content = f"""User-agent: *
Disallow: /admin/
Disallow: /staff/

Sitemap: {settings.DOMAIN_URL}/sitemap.xml
"""
    return HttpResponse(content, content_type="text/plain")

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Main App URLs
    path('', include('jobs.urls')),
    
    # SEO: Sitemap & Robots
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt),
]

# Serve media files (images) during development/debug
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
