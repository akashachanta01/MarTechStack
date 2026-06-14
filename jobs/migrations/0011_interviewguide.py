# Hand-written: a brand-new InterviewGuide table. Production is ahead of the
# migration history, so a fresh CreateModel for a new table is the safe pattern
# (it doesn't touch any existing/uncaptured tables).

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0010_pendingsubscriber"),
    ]

    operations = [
        migrations.CreateModel(
            name="InterviewGuide",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("intro", models.TextField(blank=True)),
                ("prep_tips", models.TextField(blank=True)),
                ("questions", models.JSONField(blank=True, default=list)),
                ("meta_title", models.CharField(blank=True, max_length=200)),
                ("meta_description", models.CharField(blank=True, max_length=300)),
                ("is_published", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tool", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="interview_guide", to="jobs.tool")),
            ],
        ),
    ]
