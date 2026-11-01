from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jobs", "0029_hubspot_vs_salesforce_meta")]
    operations = [
        migrations.CreateModel(
            name="HiringSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("month", models.DateField(unique=True)),
                ("data", models.JSONField(default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-month"]},
        ),
    ]
