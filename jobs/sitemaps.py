from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Job

class JobSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8
    protocol = 'https'

    def items(self):
        # Only list ACTIVE and APPROVED jobs to Google
        return Job.objects.filter(is_active=True, screening_status='approved')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('job_detail', args=[obj.id, obj.slug])
