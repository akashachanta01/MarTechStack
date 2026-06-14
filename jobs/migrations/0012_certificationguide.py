# Hand-written: a brand-new CertificationGuide table. Production is ahead of the
# migration history, so a fresh CreateModel for a new table is the safe pattern
# (it doesn't touch any existing/uncaptured tables).

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0011_interviewguide"),
    ]

    operations = [
        migrations.CreateModel(
            name="CertificationGuide",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("cert_name", models.CharField(max_length=200)),
                ("provider", models.CharField(blank=True, max_length=100)),
                ("cost", models.CharField(blank=True, max_length=100)),
                ("exam_format", models.CharField(blank=True, max_length=200)),
                ("validity", models.CharField(blank=True, max_length=100)),
                ("difficulty", models.CharField(blank=True, max_length=50)),
                ("intro", models.TextField(blank=True)),
                ("who_should_get", models.TextField(blank=True)),
                ("study_path", models.JSONField(blank=True, default=list)),
                ("exam_topics", models.JSONField(blank=True, default=list)),
                ("prep_tips", models.TextField(blank=True)),
                ("meta_title", models.CharField(blank=True, max_length=200)),
                ("meta_description", models.CharField(blank=True, max_length=300)),
                ("is_published", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tool", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="cert_guide", to="jobs.tool")),
            ],
        ),
    ]
