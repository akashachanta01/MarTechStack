# Hand-written (Sprint 3b). The production DB is ahead of migration history, so
# makemigrations would emit a giant catch-up migration. A fresh CreateModel plus
# AddFields with safe defaults is non-colliding and reversible.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0007_savedsearch"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="external_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="job",
            name="country",
            field=models.CharField(blank=True, default="", max_length=2),
        ),
        migrations.AddField(
            model_name="job",
            name="region",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="job",
            name="remote_scope",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.CreateModel(
            name="CompanySource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(help_text="Display company name", max_length=200)),
                ("ats_type", models.CharField(db_index=True, max_length=20, choices=[
                    ("greenhouse", "Greenhouse"), ("lever", "Lever"), ("ashby", "Ashby"),
                    ("workable", "Workable"), ("smartrecruiters", "SmartRecruiters"),
                    ("recruitee", "Recruitee"), ("workday", "Workday"),
                ])),
                ("token", models.CharField(blank=True, default="", max_length=200)),
                ("board_url", models.URLField(blank=True, default="", max_length=500)),
                ("enabled", models.BooleanField(db_index=True, default=True)),
                ("last_polled_at", models.DateTimeField(blank=True, null=True)),
                ("last_seen_count", models.IntegerField(default=0)),
                ("last_added_count", models.IntegerField(default=0)),
                ("consecutive_empty", models.IntegerField(default=0)),
                ("notes", models.CharField(blank=True, default="", max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name_plural": "Company sources",
                "ordering": ["last_polled_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="companysource",
            constraint=models.UniqueConstraint(fields=["ats_type", "token"], name="jobs_cs_ats_token_uniq"),
        ),
        migrations.AddIndex(
            model_name="companysource",
            index=models.Index(fields=["enabled", "last_polled_at"], name="jobs_cs_enabled_polled_idx"),
        ),
    ]
