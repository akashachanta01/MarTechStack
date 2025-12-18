from django.core.mail import EmailMessage
from django.conf import settings
from .models import Subscriber
import threading

def send_welcome_email(to_email):
    """
    Sends a welcome confirmation to a new subscriber.
    """
    def _send():
        try:
            subject = "Welcome to MarTechStack Alerts! 🚀"
            body = f"""
Hi there,

You're officially confirmed! 

You will now receive instant alerts whenever a new Marketing Operations or MarTech role is posted on MarTechStack.io.

We curate for quality, so you won't get spammed with irrelevant "Digital Marketing" or "Social Media" roles—only the technical stuff.

Best,
The MarTechStack Team
{settings.DOMAIN_URL}
            """
            
            # Send the email
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[to_email]
            )
            email.send(fail_silently=False)
            print(f"✅ Welcome email sent to {to_email}")

        except Exception as e:
            print(f"❌ Welcome Email Error: {e}")

    # Run in background to keep the popup fast
    threading.Thread(target=_send).start()

def send_job_alert(job):
    """
    Sends an email to all subscribers about a new job.
    """
    def _send():
        try:
            subscribers = list(Subscriber.objects.values_list('email', flat=True))
            
            if not subscribers:
                print("📭 No subscribers to email.")
                return

            print(f"📧 Sending alert to {len(subscribers)} subscribers for {job.title}...")

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

            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.DEFAULT_FROM_EMAIL], # Send to self
                bcc=subscribers # Blind copy everyone else
            )
            
            email.send(fail_silently=False)
            print(f"✅ Job alerts sent successfully!")

        except Exception as e:
            print(f"❌ Email Error: {e}")

    threading.Thread(target=_send).start()
