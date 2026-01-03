from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils.feedgenerator import Rss201rev2Feed
from .models import Job

class LatestJobsFeed(Feed):
    title = "MarTechJobs — Latest Roles"
    link = "/"
    description = "The freshest Marketing Operations, Technology, and Analytics jobs."
    feed_type = Rss201rev2Feed

    def items(self):
        # Return the 50 most recent approved jobs
        return Job.objects.filter(
            is_active=True, 
            screening_status='approved'
        ).order_by('-created_at')[:50]

    def item_title(self, item):
        return f"{item.title} at {item.company}"

    def item_description(self, item):
        return item.description

    def item_link(self, item):
        return reverse('job_detail', args=[item.id, item.slug])

    def item_pubdate(self, item):
        return item.created_at
