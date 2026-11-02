"""Founder rule (Nov 2 2026): never email achantaa9@gmail.com. Take it off the newsletter
list (soft unsubscribe, so it can't be silently resurrected). Sending is also blocked in
code by jobs.mail_backend.GuardedEmailBackend. Login accounts are not touched."""
from django.db import migrations
from django.utils import timezone

ADDRESS = "achantaa9@gmail.com"


def forwards(apps, schema_editor):
    apps.get_model("jobs", "Subscriber").objects.filter(email__iexact=ADDRESS).update(
        is_active=False, unsubscribed_at=timezone.now())
    apps.get_model("jobs", "PendingSubscriber").objects.filter(email__iexact=ADDRESS).delete()


class Migration(migrations.Migration):
    dependencies = [("jobs", "0032_platform_comparison_meta")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
