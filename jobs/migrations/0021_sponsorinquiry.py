from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jobs", "0020_searchconsole")]
    operations = [
        migrations.CreateModel(
            name="SponsorInquiry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("company", models.CharField(max_length=200)),
                ("name", models.CharField(max_length=200)),
                ("email", models.EmailField(max_length=254)),
                ("option", models.CharField(choices=[("newsletter", "Weekly email sponsor"), ("tool_page", "Tool page sponsor"), ("featured", "Featured company roles"), ("other", "Not sure yet / other")], default="other", max_length=20)),
                ("message", models.TextField(blank=True)),
                ("handled", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"], "verbose_name_plural": "Sponsor inquiries"},
        ),
    ]
