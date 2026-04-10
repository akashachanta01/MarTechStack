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
        body=text_content, 
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
    """
    Removed threading. Send synchronously to guarantee Render 
    doesn't kill the process before the SMTP handshake finishes.
    """
    success = send_html_email(
        subject="Welcome to MarTechJobs Alerts! 🚀",
        template_name="emails/welcome.html",
        context={},
        to_email=[to_email]
    )
    if success:
        print(f"✅ Welcome email sent to {to_email}")

def send_admin_new_subscriber_alert(subscriber_email, user_agent, ip_address):
    """
    Send admin alert synchronously.
    """
    try:
        admin_email = getattr(settings, 'EMAIL_HOST_USER', 'martechjobs@gmail.com')
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
        subscribers = list(Subscriber.objects.values_list('email', flat=True))
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
        subscribers = list(Subscriber.objects.values_list('email', flat=True))
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
