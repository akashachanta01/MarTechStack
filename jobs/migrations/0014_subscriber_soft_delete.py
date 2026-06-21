from django.db import migrations, models


class Migration(migrations.Migration):
    """Soft-delete support for newsletter subscribers (GDPR/CAN-SPAM suppression).

    Unsubscribe now flips is_active=False and stamps unsubscribed_at instead of
    deleting the row, so a suppressed address can't be silently re-added and all
    digests filter on is_active=True.

    NOTE: Following the same convention as 0006 — the production DB is ahead of
    the migration history: the `jobs_subscriber` table already exists (created
    outside tracked migrations) and is therefore NOT in Django's migration
    state. So we first register the existing model in STATE only (no DB op),
    then AddField the two genuinely-new columns (which DO hit the DB).
    """

    dependencies = [
        ("jobs", "0013_job_went_live_at_digest_sent"),
    ]

    operations = [
        # Reconcile state with the table that already exists in production.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Subscriber",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("email", models.EmailField(max_length=254, unique=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                    ],
                ),
            ],
            database_operations=[],  # table already exists — no DB change
        ),
        # Genuinely-new columns: applied to both state and the database.
        migrations.AddField(
            model_name="subscriber",
            name="is_active",
            field=models.BooleanField(default=True, db_index=True),
        ),
        migrations.AddField(
            model_name="subscriber",
            name="unsubscribed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
