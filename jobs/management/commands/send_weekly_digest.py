from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from datetime import timedelta
import time

from jobs.models import Job
from jobs.emails import _unsubscribe_url, get_digest_recipients

class Command(BaseCommand):
    help = 'Sends the weekly curated job digest to all active subscribers.'

    def handle(self, *args, **options):
        self.stdout.write("📧 Booting up the Newsletter Engine...")

        # 1. Get jobs from the last 7 days
        one_week_ago = timezone.now() - timedelta(days=7)
        # Window on went_live_at (when the job became visible), matching the
        # daily digest — created_at misses jobs approved after ingestion.
        top_jobs = Job.objects.filter(
            is_active=True,
            screening_status='approved',
            went_live_at__gte=one_week_ago
        ).order_by('-is_featured', '-went_live_at')[:10] # Top 10 jobs

        if not top_jobs.exists():
            self.stdout.write(self.style.WARNING("⚠️ No new jobs this week. Skipping email blast."))
            return

        # 2. Recipients = active subscribers + opted-in account holders,
        # minus explicit unsubscribes (shared with the daily digest).
        subscribers = get_digest_recipients()
        total_subs = len(subscribers)
        self.stdout.write(f"📫 Found {total_subs} active subscribers. Preparing to send...")

        # 3. Prepare the shared template context. The unsubscribe link must be
        # per-recipient (a signed token), so it's added inside the send loop —
        # not baked into a single shared render. Without it the digest had no
        # working unsubscribe and would fail Gmail/Yahoo bulk-sender rules.
        domain = getattr(settings, 'DOMAIN_URL', 'https://martechjobs.io')
        base_context = {
            'jobs': top_jobs,
            # Template (emails/digest.html) reads `count` in the H1/preheader —
            # passing only `job_count` left a blank number in the subject line.
            'count': top_jobs.count(),
            'job_count': top_jobs.count(),
            'domain': domain,
        }
        text_content = f"Here are your top {top_jobs.count()} MarTech Jobs this week! Visit martechjobs.io to apply."

        # 4. Send Emails (with a slight delay to avoid spam filters/rate limits)
        success_count = 0
        for email in subscribers:
            try:
                unsub_url = _unsubscribe_url(email)
                html_content = render_to_string(
                    'emails/digest.html',
                    {**base_context, 'unsubscribe_url': unsub_url},
                )
                msg = EmailMultiAlternatives(
                    subject="🔥 Top MarTech Jobs of the Week",
                    body=text_content,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'hello@martechjobs.io'),
                    to=[email],
                    headers={
                        "List-Unsubscribe": f"<{unsub_url}>",
                        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                    },
                )
                msg.attach_alternative(html_content, "text/html")
                msg.send(fail_silently=False)
                success_count += 1

                # Sleep for 0.5 seconds between emails to respect SMTP limits
                time.sleep(0.5)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Failed to send to {email}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"✨ Weekly Digest Complete! Sent to {success_count}/{total_subs} subscribers."))
