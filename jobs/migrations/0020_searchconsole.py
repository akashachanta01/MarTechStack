from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jobs", "0019_blog_job_titles_meta")]
    operations = [
        migrations.CreateModel(
            name="SearchConsoleDaily",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(unique=True)),
                ("clicks", models.IntegerField(default=0)),
                ("impressions", models.IntegerField(default=0)),
                ("ctr", models.FloatField(default=0)),
                ("position", models.FloatField(default=0)),
            ],
            options={"ordering": ["-date"]},
        ),
        migrations.CreateModel(
            name="SearchConsoleRow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("query", models.CharField(max_length=500)),
                ("page", models.URLField(max_length=500)),
                ("clicks", models.IntegerField(default=0)),
                ("impressions", models.IntegerField(default=0)),
                ("ctr", models.FloatField(default=0)),
                ("position", models.FloatField(default=0)),
                ("period_end", models.DateField()),
            ],
            options={"indexes": [models.Index(fields=["-impressions"], name="jobs_gsc_impr_idx")]},
        ),
    ]
