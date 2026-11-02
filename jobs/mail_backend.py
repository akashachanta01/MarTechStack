"""Outgoing-mail guard: addresses the site must never email (founder rule, Nov 2 2026:
"Never use achantaa9@gmail.com"). Every message passes through this backend, so no
digest, alert, welcome or admin email can reach a blocked address, whichever code sent it.
The real delivery backend is settings.EMAIL_DELIVERY_BACKEND."""
from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend


def _canonical(addr):
    addr = (addr or "").strip().lower()
    if "<" in addr and ">" in addr:
        addr = addr[addr.index("<") + 1:addr.index(">")]
    local, _, domain = addr.partition("@")
    local = local.split("+", 1)[0]
    if domain in ("gmail.com", "googlemail.com"):
        local, domain = local.replace(".", ""), "gmail.com"
    return f"{local}@{domain}"


def is_blocked(addr):
    blocked = {_canonical(a) for a in getattr(settings, "NEVER_EMAIL", ())}
    return _canonical(addr) in blocked


def strip_blocked(message):
    """Remove blocked addresses from to/cc/bcc/reply_to. Returns True if anyone is left to send to."""
    message.to = [a for a in message.to if not is_blocked(a)]
    message.cc = [a for a in message.cc if not is_blocked(a)]
    message.bcc = [a for a in message.bcc if not is_blocked(a)]
    message.reply_to = [a for a in message.reply_to if not is_blocked(a)]
    return bool(message.to or message.cc or message.bcc)


class GuardedEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.inner = get_connection(settings.EMAIL_DELIVERY_BACKEND, fail_silently=fail_silently, **kwargs)

    def open(self):
        return self.inner.open()

    def close(self):
        return self.inner.close()

    def send_messages(self, email_messages):
        keep = [m for m in (email_messages or []) if strip_blocked(m)]
        if not keep:
            return 0
        return self.inner.send_messages(keep)
