import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Saved resume text for Resume Match (brand-new table)."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0004_prowaitlistentry"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserResume",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.TextField()),
                ("filename", models.CharField(blank=True, max_length=200)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="resume", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
