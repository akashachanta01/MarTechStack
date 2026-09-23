from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0017_atscheck"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="source_key",
            field=models.CharField(blank=True, db_index=True, default="", max_length=250),
        ),
        migrations.AddField(
            model_name="job",
            name="last_seen_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
