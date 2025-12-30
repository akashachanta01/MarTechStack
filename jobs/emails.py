from django.core.mail import EmailMessage
from django.conf import settings
from .models import Subscriber
import threading
from django.utils import timezone

def send_welcome_email(to_email):
    """
    Sends a welcome confirmation to a new subscriber (Background Thread).
    """
    def _send():
        try:
            subject = "Welcome to MarTechStack Alerts! 🚀"
            body = f"""
Hi there,

You're officially confirmed! 

You will now receive instant alerts whenever a new MarTech role is posted on MarTechStack.io.

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
            print(f"✅ Welcome email sent to {to_email}")

        except Exception as e:
            print(f"❌ Welcome Email Error: {e}")

    threading.Thread(target=_send).start()

def send_admin_new_subscriber_alert(subscriber_email, user_agent, ip_address):
    """
    Notifies the Admin (hello@martechstack.io) when a new user subscribes.
    """
    def _send():
        try:
            subject = f"🔔 New Subscriber: {subscriber_email}"
            
            body = f"""
New subscriber just joined!

📧 Email: {subscriber_email}
📅 Time: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
🌍 IP Address: {ip_address}
💻 User Agent: {user_agent}

Total Subscribers: {Subscriber.objects.count()}

--------------------------------------------------
MarTechStack Admin Notification
            """

            # We send this TO the admin email (EMAIL_HOST_USER)
            admin_email = getattr(settings, 'EMAIL_HOST_USER', 'hello@martechstack.io')

            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[admin_email]
            )
            
            email.send(fail_silently=False)
            print(f"✅ Admin notification sent for {subscriber_email}")

        except Exception as e:
            print(f"❌ Admin Notification Error: {e}")

    threading.Thread(target=_send).start()

def send_job_alert(job):
    """
    Sends an email to all subscribers about a new job (Background Thread).
    """
    def _send():
        try:
            subscribers = list(Subscriber.objects.values_list('email', flat=True))
            
            if not subscribers:
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

            # Send to self, BCC everyone else to protect privacy
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.DEFAULT_FROM_EMAIL], 
                bcc=subscribers 
            )
            
            email.send(fail_silently=False)
            print(f"✅ Job alerts sent successfully!")

        except Exception as e:
            print(f"❌ Email Error: {e}")

    threading.Thread(target=_send).start()
