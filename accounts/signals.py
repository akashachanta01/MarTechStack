# Signal handlers. Imported by apps.py (AccountsConfig.ready) so they register.
from allauth.account.signals import user_signed_up
from django.dispatch import receiver

from accounts.models import ensure_user_profile  # noqa: F401
from accounts.emails import send_account_welcome_email, send_admin_new_user_alert


@receiver(user_signed_up)
def on_user_signed_up(request, user, **kwargs):
    """Fires once per new account (email OR Google). Sends the user a welcome
    email and notifies the founder. Both calls are internally non-fatal so a
    mail hiccup never breaks the signup."""
    send_account_welcome_email(user)
    send_admin_new_user_alert(user)
