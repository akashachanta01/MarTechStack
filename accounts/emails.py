import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from jobs.emails import send_welcome_email

logger = logging.getLogger('jobs')


def send_account_welcome_email(user):
    """Welcome the new account holder. Reuses the same branded welcome
    template the subscribe flow uses. Non-fatal — never breaks signup."""
    try:
        if user.email:
            send_welcome_email(user.email)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("Account welcome email failed for %s: %s", user.email, e)


def send_pro_waitlist_alert(user):
    """Notify the founder when a user joins the Go Pro waitlist (demand signal).
    Non-fatal."""
    try:
        admin_email = (getattr(settings, 'CONTACT_EMAIL', None)
                       or getattr(settings, 'EMAIL_HOST_USER', 'hello@martechjobs.io'))
        from .models import UserProfile
        total = UserProfile.objects.filter(pro_waitlist=True).count()
        body = (
            "New Go Pro waitlist signup\n\n"
            f"Name:  {user.get_full_name() or '—'}\n"
            f"Email: {user.email}\n"
            f"When:  {timezone.now()}\n"
            f"Total on waitlist: {total}\n"
        )
        msg = EmailMultiAlternatives(
            subject=f"⭐ Go Pro waitlist: {user.email}",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[admin_email],
        )
        msg.send(fail_silently=True)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("Pro waitlist alert failed: %s", e)


def send_admin_new_user_alert(user):
    """Notify the founder that a new account was created, with live totals. Non-fatal."""
    try:
        from jobs.emails import audience_totals, _founder_email
        from jobs.models import Subscriber
        accounts, subscribers = audience_totals()
        method = "Email + password"
        try:
            from allauth.socialaccount.models import SocialAccount
            providers = list(SocialAccount.objects.filter(user=user).values_list("provider", flat=True))
            if providers:
                method = ", ".join(p.title() for p in providers)
        except Exception:
            pass
        subscribed = Subscriber.objects.filter(email__iexact=user.email, is_active=True).exists()
        body = (
            "New account created on MarTechJobs\n\n"
            f"Name:          {user.get_full_name() or '—'}\n"
            f"Email:         {user.email}\n"
            f"Signed up via: {method}\n"
            f"Newsletter:    {'Subscribed' if subscribed else 'Not subscribed'}\n"
            f"When:          {timezone.now():%d %b %Y, %H:%M} UTC\n\n"
            f"Total accounts:     {accounts}\n"
            f"Total subscribers:  {subscribers}\n"
        )
        EmailMultiAlternatives(subject=f"[MTJ] New account: {user.email}", body=body,
                               from_email=settings.DEFAULT_FROM_EMAIL, to=[_founder_email()]).send(fail_silently=True)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("Admin new-user alert failed: %s", e)
