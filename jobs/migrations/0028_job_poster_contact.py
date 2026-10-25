from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jobs", "0027_lowercase_cert_guide_slugs")]
    operations = [
        migrations.AddField("job", "poster_name", models.CharField(blank=True, default="", max_length=120)),
        migrations.AddField("job", "poster_email", models.EmailField(blank=True, default="", max_length=254)),
        migrations.AddField("job", "poster_role", models.CharField(
            blank=True, default="", max_length=20,
            choices=[("in_house", "In-house recruiter / HR"), ("hiring_manager", "Hiring manager"),
                     ("agency", "Agency recruiter"), ("other", "Other")])),
    ]
