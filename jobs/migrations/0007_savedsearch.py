# Hand-written to add ONLY the new SavedSearch table.
# The production DB is ahead of the migration history, so letting makemigrations
# auto-generate would produce a giant "catch-up" migration that collides with
# existing tables. A fresh CreateModel for a brand-new table is safe.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0006_add_function_field"),
    ]

    operations = [
        migrations.CreateModel(
            name="SavedSearch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("query", models.CharField(blank=True, default="", max_length=200)),
                ("tool", models.CharField(blank=True, default="", max_length=100)),
                ("location", models.CharField(blank=True, default="", max_length=120)),
                ("function", models.CharField(blank=True, default="", max_length=20)),
                ("arrangement", models.CharField(blank=True, default="", max_length=20)),
                ("label", models.CharField(blank=True, default="", max_length=200)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_notified_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name_plural": "Saved searches",
            },
        ),
        migrations.AddIndex(
            model_name="savedsearch",
            index=models.Index(fields=["email", "is_active"], name="jobs_ss_email_active_idx"),
        ),
    ]
