from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0002_job_salary_range_job_tags_subscriber"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="screening_status",
            field=models.CharField(
                choices=[("pending", "Pending Review"), ("approved", "Approved"), ("rejected", "Rejected")],
                db_index=True,
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="job",
            name="screening_score",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="job",
            name="screening_reason",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="job",
            name="screening_details",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="job",
            name="screened_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="BlockRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "rule_type",
                    models.CharField(
                        choices=[("domain", "Domain"), ("company", "Company"), ("keyword", "Keyword"), ("regex", "Regex (title/description)")],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("value", models.CharField(help_text="Value for the rule (domain/company/keyword/regex).", max_length=500)),
                ("enabled", models.BooleanField(default=True)),
                ("notes", models.CharField(blank=True, default="", max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
