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


def send_admin_new_user_alert(user):
    """Notify the founder that a new account was created. Non-fatal."""
    try:
        admin_email = (getattr(settings, 'CONTACT_EMAIL', None)
                       or getattr(settings, 'EMAIL_HOST_USER', 'martechjobs@gmail.com'))
        body = (
            "New account created on MarTechJobs\n\n"
            f"Name:  {user.get_full_name() or '—'}\n"
            f"Email: {user.email}\n"
            f"When:  {timezone.now()}\n"
            f"Total users: {User.objects.count()}\n"
        )
        msg = EmailMultiAlternatives(
            subject=f"🎉 New account: {user.email}",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[admin_email],
        )
        msg.send(fail_silently=True)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("Admin new-user alert failed: %s", e)
