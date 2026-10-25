"""Sign-up form with free, invisible bot checks.

Oct 2026 audit: ~44 of 121 accounts were bots signing up with other people's
email addresses (generic names like "Ava Martin" on unrelated addresses, junk
like "LoganwhorbRW" or "Wademe vyjaver ... y7 martechjobs.io"). Real people
never see these checks:
- honeypot: a hidden field humans can't see; bots fill every field
- timing: a signed timestamp; submitting within 3 seconds of loading is a script
- junk names: digits, links, or bot-style names are refused
- per-IP limit: at most 3 sign-ups an hour from one address
"""
import logging
import re
import time

from allauth.account.forms import SignupForm
from django import forms
from django.core import signing

logger = logging.getLogger("jobs")

MIN_SECONDS = 3
TS_SALT = "signup-ts"
_JUNK_NAME = re.compile(r"\d|https?:|www\.|\.(com|io|net|org|ru|ua)\b|[<>@/]", re.I)
_BOT_CASE = re.compile(r"^[A-Z][a-z]{4,}[A-Z]{2,}$")  # e.g. LoganwhorbRW, RaymonddydayEL
GENERIC_ERROR = "Sorry, we couldn't create your account. Please try again in a minute."


def signup_token():
    return signing.dumps(int(time.time()), salt=TS_SALT)


def bot_reason(data):
    """Why this sign-up looks automated, or '' if it looks human."""
    if (data.get("website") or "").strip():
        return "honeypot"
    try:
        started = signing.loads(data.get("ts") or "", salt=TS_SALT, max_age=86400)
    except signing.BadSignature:
        return "no_token"
    if time.time() - started < MIN_SECONDS:
        return "too_fast"
    first, last = (data.get("first_name") or "").strip(), (data.get("last_name") or "").strip()
    for name in (first, last):
        if len(name) > 40 or _JUNK_NAME.search(name) or _BOT_CASE.match(name):
            return "junk_name"
    if first and first == last and len(first) > 6:
        return "junk_name"
    return ""


class BotCheckSignupForm(SignupForm):
    website = forms.CharField(required=False)  # honeypot, hidden in the template
    ts = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from allauth.core import context
        self.request = context.request  # set per request by allauth's AccountMiddleware
        if not self.is_bound:
            self.initial["ts"] = signup_token()
        self.fields["ts"].initial = self.initial.get("ts") or signup_token()

    def clean(self):
        cleaned = super().clean()
        reason = bot_reason(self.data)
        if not reason and self.request is not None:
            from jobs.views import _rate_limited
            if _rate_limited(self.request, "signup", limit=3, window_seconds=3600):
                reason = "rate_limited"
        if reason:
            self.bot_reason = reason
            logger.warning("Sign-up blocked (%s): %s", reason, (self.data.get("email") or "")[:80])
            try:
                from jobs.server_analytics import capture
                capture("signup_blocked", self.request, {"reason": reason})
            except Exception:
                pass
            raise forms.ValidationError(GENERIC_ERROR)
        return cleaned
