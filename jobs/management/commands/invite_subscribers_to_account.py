"""
One-time (per-subscriber) campaign: invite newsletter subscribers who DON'T
have an account yet to create a free one. Targets exactly the founder's
"subscribed but no account" segment.

Guards baked in:
- Only active subscribers (is_active=True) — never emails a suppressed address.
- Skips anyone who already has a User account (they converted).
- Skips anyone already invited (account_invite_sent_at set) — safe to re-run;
  it resumes where it left off and never double-emails.
- --limit lets you drip the campaign (protects Resend/deliverability rep).

  python manage.py invite_subscribers_to_account                 # dry run
  python manage.py invite_subscribers_to_account --limit 50      # preview 50
  python manage.py invite_subscribers_to_account --limit 50 --confirm
"""

import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model

from jobs.models import Subscriber
from jobs.emails import send_html_email


class Command(BaseCommand):
    help = "Invite account-less newsletter subscribers to create a free account."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", help="Actually send (default dry run).")
        parser.add_argument("--limit", type=int, default=100, help="Max invites this run (default 100).")

    def handle(self, *args, **options):
        confirm = options["confirm"]
        limit = options["limit"]

        User = get_user_model()
        account_emails = {e.lower() for e in User.objects.values_list("email", flat=True) if e}

        candidates = []
        for sub in Subscriber.objects.filter(
            is_active=True, account_invite_sent_at__isnull=True
        ).order_by("created_at"):
            if (sub.email or "").lower() in account_emails:
                continue  # already has an account
            candidates.append(sub)
            if len(candidates) >= limit:
                break

        self.stdout.write(f"Account-less active subscribers to invite this run: {len(candidates)}")
        for s in candidates[:10]:
            self.stdout.write(f"  • {s.email}")
        if len(candidates) > 10:
            self.stdout.write(f"  … and {len(candidates) - 10} more")

        if not confirm:
            self.stdout.write(self.style.WARNING("Dry run — re-run with --confirm to send."))
            return

        sent = 0
        for sub in candidates:
            ok = send_html_email(
                subject="Get more from MarTechJobs — create your free account",
                template_name="emails/invite_account.html",
                context={"subscriber_email": sub.email},
                to_email=[sub.email],
                unsubscribe_email=sub.email,
            )
            if ok:
                sub.account_invite_sent_at = timezone.now()
                sub.save(update_fields=["account_invite_sent_at"])
                sent += 1
            time.sleep(0.3)

        self.stdout.write(self.style.SUCCESS(f"✨ Sent {sent}/{len(candidates)} account invites."))
