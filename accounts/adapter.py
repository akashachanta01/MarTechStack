import logging

from allauth.account.adapter import DefaultAccountAdapter

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
