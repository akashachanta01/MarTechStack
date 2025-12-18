from django.core.mail import EmailMessage
from django.conf import settings
from .models import Subscriber
import threading

def send_job_alert(job):
    """
    Sends an email to all subscribers about a new job.
    Runs in a background thread to prevent slowing down the response.
    """
    def _send():
        try:
            # 1. Get all subscriber emails
            subscribers = list(Subscriber.objects.values_list('email', flat=True))
            
            if not subscribers:
                print("📭 No subscribers to email.")
                return

            print(f"📧 Sending alert to {len(subscribers)} subscribers for {job.title}...")

            # 2. Construct the Email
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

            # 3. Send (Using BCC to hide recipient list)
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.DEFAULT_FROM_EMAIL], # Send to self
                bcc=subscribers # Blind copy everyone else
            )
            
            email.send(fail_silently=False)
            print(f"✅ Emails sent successfully!")

        except Exception as e:
            print(f"❌ Email Error: {e}")

    # Run in a separate thread so we don't block the webhook/admin page
    threading.Thread(target=_send).start()
