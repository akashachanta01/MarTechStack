from django.core.mail import EmailMessage
from django.conf import settings
from .models import Subscriber

def send_welcome_email(to_email):
    """
    Sends a welcome confirmation to a new subscriber.
    Running synchronously to ensure reliability and logging.
    """
    print(f"📨 EMAILER: Preparing to send Welcome Email to {to_email}...", flush=True)
    
    try:
        subject = "Welcome to MarTechStack Alerts! 🚀"
        body = f"""
Hi there,

You're officially confirmed! 

You will now receive instant alerts whenever a new Marketing Operations or MarTech role is posted on MarTechStack.io.

We curate for quality, so you won't get spammed with irrelevant roles—only the technical stuff.

Best,
The MarTechStack Team
{settings.DOMAIN_URL}
        """
        
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email]
        )
        email.send(fail_silently=False)
        print("✅ EMAILER: Welcome email sent successfully!", flush=True)

    except Exception as e:
        print(f"❌ EMAILER ERROR (Welcome): {e}", flush=True)

def send_job_alert(job):
    """
    Sends an email to all subscribers about a new job.
    """
    print(f"📨 EMAILER: Preparing Job Alert for '{job.title}'...", flush=True)
    
    try:
        # 1. Get Subscribers
        subscribers = list(Subscriber.objects.values_list('email', flat=True))
        
        if not subscribers:
            print("📭 EMAILER: No subscribers found. Skipping.", flush=True)
            return

        print(f"   - Found {len(subscribers)} subscribers.", flush=True)

        # 2. Build Email
        subject = f"New Role: {job.title} at {job.company}"
        
        body = f"""
New opportunity on MarTechStack:

Role: {job.title}
Company: {job.company}
Location: {job.location}
Salary: {job.salary_range or "Not listed"}

View Job: {settings.DOMAIN_URL}/?q={job.title.replace(' ', '+')}

--------------------------------------------------
You are receiving this because you subscribed to MarTechStack alerts.
        """

        # 3. Send (Using BCC to protect privacy)
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.DEFAULT_FROM_EMAIL], # Send to self
            bcc=subscribers # Blind copy everyone else
        )
        
        email.send(fail_silently=False)
        print("✅ EMAILER: Job alert sent successfully!", flush=True)

    except Exception as e:
        print(f"❌ EMAILER ERROR (Job Alert): {e}", flush=True)
