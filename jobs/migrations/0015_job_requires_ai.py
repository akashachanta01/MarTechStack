from django.db import migrations, models


class Migration(migrations.Migration):
    """AI overlay flag on jobs: powers the cross-cutting AI & Automation
    category (/category/ai-automation/). Scoped to only this field — the
    known model/migration drift on other fields is deliberately untouched
    (see BACKLOG.md: migration history baseline reset)."""

    dependencies = [
        ("jobs", "0014_subscriber_soft_delete"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="requires_ai",
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]
