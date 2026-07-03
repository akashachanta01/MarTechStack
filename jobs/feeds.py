from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils.feedgenerator import Rss201rev2Feed
from .models import Job, BlogPost

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


class BlogFeed(Feed):
    """RSS feed of published blog posts. Exists so no-code automation
    (Buffer/Zapier/Make) can watch it and auto-share each new post to the
    LinkedIn company page — the ToS-compliant way to automate LinkedIn."""
    title = "MarTechJobs Blog — MarTech Careers, Salaries & AI"
    link = "/blog/"
    description = "Guides and analysis on Marketing Operations, MarTech careers, salaries, and AI in marketing technology."
    feed_type = Rss201rev2Feed

    def items(self):
        return BlogPost.objects.filter(is_published=True).order_by('-published_at')[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.excerpt or item.meta_description or item.title

    def item_link(self, item):
        return reverse('post_detail', args=[item.slug])

    def item_pubdate(self, item):
        # published_at is a DateField on BlogPost; feeds want a datetime.
        import datetime
        from django.utils import timezone as djtz
        d = item.published_at
        if isinstance(d, datetime.datetime):
            return d
        return djtz.make_aware(datetime.datetime.combine(d, datetime.time(9, 0)))
