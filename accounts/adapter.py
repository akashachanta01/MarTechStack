import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

logger = logging.getLogger('jobs')


class AccountAdapter(DefaultAccountAdapter):

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        # Capture name fields passed from our custom signup template.
        user.first_name = request.POST.get('first_name', '').strip()[:30]
        user.last_name = request.POST.get('last_name', '').strip()[:150]
        if commit:
            user.save()
        return user

    def send_mail(self, template_prefix, email, context):
        # Email verification is OPTIONAL, so a transient SMTP failure must
        # never break the signup/critical path. Send best-effort and log on
        # failure instead of letting the exception bubble up into a 500.
        try:
            super().send_mail(template_prefix, email, context)
        except Exception as e:
            logger.warning("allauth email send failed (%s): %s", template_prefix, e)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Auto-link Google logins to a pre-existing local account with the same
    email, so a user who first signed up with email/password can later click
    "Sign in with Google" and land straight in their account — instead of
    being bounced to a signup screen. Safe because Google supplies a verified
    email (proof of ownership)."""

    def pre_social_login(self, request, sociallogin):
        # Already linked (returning Google user) → let allauth proceed.
        if sociallogin.is_existing:
            return

        email = (sociallogin.user.email or '').strip().lower()
        if not email:
            return

        from django.contrib.auth.models import User
        existing = User.objects.filter(email__iexact=email).first()
        if existing:
            # Connect this Google identity to the existing account and log in.
            sociallogin.connect(request, existing)

