from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    saved_jobs = models.ManyToManyField('jobs.Job', blank=True, related_name='saved_by')
    preferred_stack = models.ManyToManyField('jobs.Tool', blank=True, related_name='preferred_by')
    preferred_location = models.CharField(max_length=100, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    linkedin_url = models.URLField(blank=True)
    # Social links
    github_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    website_url = models.URLField(blank=True)
    # Job preferences
    open_to_remote = models.BooleanField(default=False)
    desired_role_type = models.CharField(max_length=20, blank=True)  # full_time / contract / part_time / ''
    desired_salary = models.CharField(max_length=60, blank=True)
    # Notification preferences (Settings page)
    email_newsletter = models.BooleanField(default=True)
    email_announcements = models.BooleanField(default=True)
    # Go Pro waitlist
    pro_waitlist = models.BooleanField(default=False)
    pro_waitlist_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile: {self.user.email}"

    def profile_complete_pct(self):
        fields = [
            bool(self.user.first_name),
            bool(self.preferred_stack.exists()),
            bool(self.preferred_location),
            bool(self.bio),
            bool(self.linkedin_url),
        ]
        done = sum(fields)
        return int((done / len(fields)) * 100)


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):
    # Guarantee every User has a profile. get_or_create covers both new
    # signups and any legacy users created before this app existed, without
    # issuing a redundant UPDATE on every User.save().
    UserProfile.objects.get_or_create(user=instance)
