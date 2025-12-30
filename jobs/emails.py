from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import Subscriber
import threading
from django.utils import timezone

def send_html_email(subject, template_name, context, to_email=None, bcc_list=None):
    """
    Helper to send HTML emails with a Plain Text fallback.
    """
    # 1. Render HTML
    html_content = render_to_string(template_name, context)
    # 2. Create Plain Text version (for spam filters)
    text_content = strip_tags(html_content)

    # 3. Setup Email
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content, # Plain text goes here
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to_email if to_email else [settings.DEFAULT_FROM_EMAIL],
        bcc=bcc_list if bcc_list else []
    )
    
    # 4. Attach HTML
    msg.attach_alternative(html_content, "text/html")
    
    # 5. Send
    try:
        msg.send(fail_silently=False)
        return True
    except Exception as e:
        print(f"❌ Email Error ({subject}): {e}")
        return False

def send_welcome_email(to_email):
    def _send():
        send_html_email(
            subject="Welcome to MarTechStack Alerts! 🚀",
            template_name="emails/welcome.html",
            context={},
            to_email=[to_email]
        )
        print(f"✅ Welcome email sent to {to_email}")
    threading.Thread(target=_send).start()

def send_job_alert(job):
    """
    Sends a Single Job Alert to ALL subscribers.
    """
    def _send():
        subscribers = list(Subscriber.objects.values_list('email', flat=True))
        if not subscribers: return

        print(f"📧 Sending SINGLE alert to {len(subscribers)} subscribers...")
        
        send_html_email(
            subject=f"New Role: {job.title} at {job.company}",
            template_name="emails/job_alert.html",
            context={'job': job},
            bcc_list=subscribers # Hidden recipients
        )
    threading.Thread(target=_send).start()

def send_digest_alert(jobs):
    """
    Sends a BATCH of jobs (Digest) to ALL subscribers.
    """
    def _send():
        subscribers = list(Subscriber.objects.values_list('email', flat=True))
        if not subscribers: return
        
        count = len(jobs)
        print(f"📧 Sending DIGEST alert ({count} jobs) to {len(subscribers)} subscribers...")
        
        send_html_email(
            subject=f"🔥 {count} New MarTech Roles: {jobs[0].title} & more...",
            template_name="emails/digest.html",
            context={'jobs': jobs, 'count': count},
            bcc_list=subscribers
        )
    threading.Thread(target=_send).start()

def send_admin_new_subscriber_alert(subscriber_email, user_agent, ip_address):
    # This one can stay plain text, it's just for you.
    def _send():
        try:
            admin_email = getattr(settings, 'EMAIL_HOST_USER', 'hello@martechstack.io')
            subject = f"🔔 New Subscriber: {subscriber_email}"
            body = f"""
New subscriber: {subscriber_email}
IP: {ip_address}
Time: {timezone.now()}
Total: {Subscriber.objects.count()}
            """
            email = EmailMultiAlternatives(subject, body, settings.DEFAULT_FROM_EMAIL, [admin_email])
            email.send()
        except: pass
    threading.Thread(target=_send).start()
