# Hand-written to add ONLY the new PendingSubscriber table.
# Production is ahead of the migration history (and the existing Subscriber
# model was never captured in a migration), so a fresh CreateModel for a
# brand-new table is the safe pattern — it doesn't touch Subscriber at all.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0009_job_external_id_unique"),
    ]

    operations = [
        migrations.CreateModel(
            name="PendingSubscriber",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("token", models.CharField(db_index=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
