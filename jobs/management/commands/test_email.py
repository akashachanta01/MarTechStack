"""
Diagnose the email/SMTP configuration.

Run in the Render shell:
  python manage.py test_email you@example.com

It prints the active email settings (password masked) and attempts to send a
real test message, surfacing the FULL exception so SMTP/auth problems are
visible instead of being swallowed silently.
"""

import traceback

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Print email config and send a test email to verify SMTP works"

    def add_arguments(self, parser):
        parser.add_argument("to", nargs="?", help="Recipient address (defaults to EMAIL_HOST_USER)")

    def handle(self, *args, **options):
        pw = getattr(settings, "EMAIL_HOST_PASSWORD", "") or ""
        to = options.get("to") or getattr(settings, "EMAIL_HOST_USER", "")

        self.stdout.write("=== EMAIL CONFIG ===")
        self.stdout.write(f"EMAIL_BACKEND      = {getattr(settings, 'EMAIL_BACKEND', '(unset)')}")
        self.stdout.write(f"EMAIL_HOST         = {getattr(settings, 'EMAIL_HOST', '(unset)')}")
        self.stdout.write(f"EMAIL_PORT         = {getattr(settings, 'EMAIL_PORT', '(unset)')}")
        self.stdout.write(f"EMAIL_USE_TLS      = {getattr(settings, 'EMAIL_USE_TLS', '(unset)')}")
        self.stdout.write(f"EMAIL_HOST_USER    = {getattr(settings, 'EMAIL_HOST_USER', '(unset)')}")
        self.stdout.write(f"EMAIL_HOST_PASSWORD= {'SET (' + str(len(pw)) + ' chars)' if pw else '*** EMPTY ***'}")
        self.stdout.write(f"DEFAULT_FROM_EMAIL = {getattr(settings, 'DEFAULT_FROM_EMAIL', '(unset)')}")
        self.stdout.write(f"Sending test to    = {to}")
        self.stdout.write("")

        if not pw:
            self.stdout.write(self.style.ERROR(
                "EMAIL_HOST_PASSWORD is empty. Set it in Render → Environment to a "
                "Gmail App Password (not your normal password). Nothing will send until this is set."
            ))
            return

        if not to:
            self.stdout.write(self.style.ERROR("No recipient. Pass one: python manage.py test_email you@example.com"))
            return

        self.stdout.write("Attempting SMTP send (fail_silently=False)...")
        try:
            connection = get_connection(fail_silently=False)
            msg = EmailMultiAlternatives(
                subject="MarTechJobs — SMTP test ✅",
                body="If you're reading this, your email configuration works.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[to],
                connection=connection,
            )
            msg.attach_alternative(
                "<p>If you're reading this, your <b>email configuration works</b>.</p>",
                "text/html",
            )
            sent = msg.send(fail_silently=False)
            if sent:
                self.stdout.write(self.style.SUCCESS(f"✅ Sent successfully to {to}. Check the inbox (and spam)."))
            else:
                self.stdout.write(self.style.ERROR("send() returned 0 — message was not delivered."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ SMTP FAILED: {type(e).__name__}: {e}"))
            self.stdout.write("")
            self.stdout.write("Full traceback:")
            self.stdout.write(traceback.format_exc())
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "Most common Gmail causes:\n"
                "  1. Using your normal password instead of an App Password.\n"
                "  2. 2-Step Verification not enabled on the Gmail account (required to create an App Password).\n"
                "  3. App Password copied with spaces — paste it WITHOUT spaces.\n"
                "  4. EMAIL_HOST_USER doesn't match the account that owns the App Password."
            ))
