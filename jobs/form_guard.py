"""Bot guard for the newsletter / job-alert subscribe endpoint.

Nov 1-2 2026: a script POSTed /subscribe/ straight from rotating residential IPs
(same Referer, random browser user agents), so the per-IP rate limit never tripped
and strangers got repeated "Confirm your subscription" emails (subscription bombing,
which hurts our sender reputation). Real visitors always submit through the page's
JavaScript, which now sends a signed page timestamp; direct POSTs don't have it.
"""
import logging
import time

from django.core import signing
from django.core.cache import cache
from django.utils import timezone

log = logging.getLogger(__name__)
SALT = "subscribe-ts"
MAX_AGE = 2 * 86400            # a page left open for up to 2 days still works
PER_EMAIL_SECONDS = 86400      # at most one confirmation email per address per day
DAILY_CONFIRMATION_CAP = 50    # hard ceiling on confirmation emails per day


def form_ts():
    return signing.dumps(int(time.time()), salt=SALT)


def block_reason(post):
    """None if the submission looks human, else a short reason string."""
    if (post.get("website") or "").strip():
        return "honeypot"
    try:
        signing.loads(post.get("ts") or "", salt=SALT, max_age=MAX_AGE)
    except signing.SignatureExpired:
        return "expired_token"
    except signing.BadSignature:
        return "no_token"
    return None


def may_send_confirmation(email):
    """True (and records the send) unless this address already got one in the last
    24h or today's overall cap is reached."""
    if not cache.add(f"confirm_sent:{email}", 1, timeout=PER_EMAIL_SECONDS):
        return False
    day_key = f"confirm_sent_day:{timezone.now():%Y-%m-%d}"
    cache.add(day_key, 0, timeout=2 * 86400)
    try:
        n = cache.incr(day_key)
    except ValueError:
        cache.add(day_key, 1, timeout=2 * 86400)
        n = 1
    if n > DAILY_CONFIRMATION_CAP:
        log.error("Confirmation email cap reached (%s today) - not sending", n)
        return False
    return True
