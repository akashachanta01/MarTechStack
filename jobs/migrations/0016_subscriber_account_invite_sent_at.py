from django.db import migrations, models


class Migration(migrations.Migration):
    """Track when a subscriber was invited to create an account, so the
    invite campaign never double-emails."""

    dependencies = [
        ("jobs", "0015_job_requires_ai"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscriber",
            name="account_invite_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
