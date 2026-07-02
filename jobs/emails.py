from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.core import signing
from .models import Subscriber
import threading
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

DOMAIN = getattr(settings, "DOMAIN_URL", "https://martechjobs.io")


def _unsubscribe_url(email):
    """Signed, per-recipient one-click unsubscribe URL."""
    token = signing.dumps(email, salt="unsubscribe")
    return f"{DOMAIN}/u/{token}/"


def get_digest_recipients():
    """The full set of emails that should receive the job digest.

    Union of two opt-in sources, minus anyone who explicitly unsubscribed:
      1. Active newsletter Subscribers (double opt-in list).
      2. Account holders whose UserProfile.email_newsletter is True
         (defaults True on signup — accounts were silently excluded before).

    Suppression: any email with a Subscriber row where is_active=False has
    unsubscribed (one-click / settings toggle). Those are removed even if the
    account's newsletter flag is still True, so an unsubscribe always wins.
    """
    from django.contrib.auth import get_user_model

    suppressed = {
        e.lower()
        for e in Subscriber.objects.filter(is_active=False).values_list("email", flat=True)
        if e
    }

    emails = set()
    for e in Subscriber.objects.filter(is_active=True).values_list("email", flat=True):
        if e and e.lower() not in suppressed:
            emails.add(e.lower())

    # Account holders opted into the newsletter (related lookup avoids importing
    # UserProfile directly — no circular import with the accounts app).
    User = get_user_model()
    account_emails = (
        User.objects.filter(userprofile__email_newsletter=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    for e in account_emails:
        if e and e.lower() not in suppressed:
            emails.add(e.lower())

    return sorted(emails)


def send_html_email(subject, template_name, context, to_email=None, bcc_list=None,
                    unsubscribe_email=None):
    """
    Helper to send HTML emails with a Plain Text fallback.

    Adds deliverability headers (List-Unsubscribe + one-click, Reply-To). These
    are what Gmail/Yahoo now look for to keep bulk mail OUT of spam. When a
    single recipient is known (welcome email), we attach a personalized signed
    unsubscribe link so one-click works.
    """
    # Guard: if SMTP credentials are missing, nothing will ever send. Surface
    # this loudly rather than failing silently per-message.
    if not getattr(settings, 'EMAIL_HOST_PASSWORD', ''):
        logger.error(
            "Email NOT sent ('%s'): EMAIL_HOST_PASSWORD is empty. "
            "Set a Gmail App Password in the environment.", subject
        )
        return False

    # Personalized unsubscribe link for the template + headers.
    unsub_url = _unsubscribe_url(unsubscribe_email) if unsubscribe_email else f"{DOMAIN}/unsubscribe/"
    context = {**context, "unsubscribe_url": unsub_url, "domain": DOMAIN}

    # 1. Render HTML
    html_content = render_to_string(template_name, context)
    # 2. Create Plain Text version (for spam filters)
    text_content = strip_tags(html_content)

    # 3. Deliverability headers
    reply_to = getattr(settings, "CONTACT_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", None)
    headers = {
        "List-Unsubscribe": f"<{unsub_url}>, <mailto:{reply_to}?subject=unsubscribe>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }

    # 4. Setup Email
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to_email if to_email else [settings.DEFAULT_FROM_EMAIL],
        bcc=bcc_list if bcc_list else [],
        reply_to=[reply_to] if reply_to else None,
        headers=headers,
    )

    # 5. Attach HTML
    msg.attach_alternative(html_content, "text/html")

    # 6. Send
    try:
        msg.send(fail_silently=False)
        return True
    except Exception as e:
        # Log the FULL exception (with traceback) so SMTP/auth failures are
        # diagnosable in the Render logs instead of a one-line print.
        logger.exception("Email send failed ('%s'): %s", subject, e)
        return False

def send_confirmation_email(to_email, token):
    """Double opt-in: ask the new subscriber to confirm before we add them to
    the sending list. No welcome until they click."""
    confirm_url = f"{DOMAIN}/newsletter/confirm/{token}/"
    success = send_html_email(
        subject="Confirm your MarTechJobs subscription",
        template_name="emails/confirm_subscription.html",
        context={"confirm_url": confirm_url},
        to_email=[to_email],
        unsubscribe_email=to_email,
    )
    if success:
        logger.info("Confirmation email sent to %s", to_email)
    return success


def send_welcome_email(to_email):
    """
    Removed threading. Send synchronously to guarantee Render
    doesn't kill the process before the SMTP handshake finishes.
    """
    success = send_html_email(
        subject="You're in — welcome to MarTechJobs",
        template_name="emails/welcome.html",
        context={},
        to_email=[to_email],
        unsubscribe_email=to_email,
    )
    if success:
        logger.info("Welcome email sent to %s", to_email)

def send_admin_new_subscriber_alert(subscriber_email, user_agent, ip_address):
    """
    Send admin alert synchronously.
    """
    try:
        admin_email = getattr(settings, 'CONTACT_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', 'martechjobs@gmail.com')
        subject = f"🔔 New Subscriber: {subscriber_email}"
        body = f"""
New subscriber: {subscriber_email}
IP: {ip_address}
Time: {timezone.now()}
Total: {Subscriber.objects.count()}
        """
        email = EmailMultiAlternatives(subject, body, settings.DEFAULT_FROM_EMAIL, [admin_email])
        email.send(fail_silently=True)
    except: 
        pass

def send_job_alert(job):
    """
    Sends a Single Job Alert to ALL subscribers.
    Kept threading here because bulk sending can take a long time, 
    but for a production app with 15k subs, consider moving this to Celery/Redis later.
    """
    def _send():
        subscribers = list(Subscriber.objects.filter(is_active=True).values_list('email', flat=True))
        if not subscribers: return

        print(f"📧 Sending SINGLE alert to {len(subscribers)} subscribers...")
        
        # Gmail limits to 100 BCCs per email. We chunk them into groups of 90.
        chunk_size = 90
        for i in range(0, len(subscribers), chunk_size):
            chunk = subscribers[i:i + chunk_size]
            send_html_email(
                subject=f"New Role: {job.title} at {job.company}",
                template_name="emails/job_alert.html",
                context={'job': job},
                bcc_list=chunk
            )
            
    threading.Thread(target=_send).start()

def send_digest_alert(jobs):
    """
    Sends a BATCH of jobs (Digest) to ALL subscribers.
    """
    def _send():
        subscribers = list(Subscriber.objects.filter(is_active=True).values_list('email', flat=True))
        if not subscribers: return

        count = len(jobs)
        print(f"📧 Sending DIGEST alert ({count} jobs) to {len(subscribers)} subscribers...")
        
        chunk_size = 90
        for i in range(0, len(subscribers), chunk_size):
            chunk = subscribers[i:i + chunk_size]
            send_html_email(
                subject=f"🔥 {count} New MarTech Roles: {jobs[0].title} & more...",
                template_name="emails/digest.html",
                context={'jobs': jobs, 'count': count},
                bcc_list=chunk
            )
            
    threading.Thread(target=_send).start()
