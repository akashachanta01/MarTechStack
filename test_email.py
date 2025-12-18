import os
import django
from django.core.mail import send_mail
from django.conf import settings

# 1. Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def send_test():
    print("--- 📧 TESTING EMAIL CONFIGURATION ---")
    print(f"User: {settings.EMAIL_HOST_USER}")
    # Don't print the password, just check if it exists
    print(f"Password set? {'Yes' if settings.EMAIL_HOST_PASSWORD else 'No'}")
    
    try:
        print("\nAttempting to send email...")
        send_mail(
            subject="Test Email from MarTechStack",
            message="If you are reading this, your email configuration is PERFECT! 🚀",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.EMAIL_HOST_USER], # Sending to yourself
            fail_silently=False,
        )
        print("✅ SUCCESS! Email sent. Check your inbox.")
    except Exception as e:
        print(f"❌ FAILED. Error details:\n{e}")

if __name__ == '__main__':
    send_test()
