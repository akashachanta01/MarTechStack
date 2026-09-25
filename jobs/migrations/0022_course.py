import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jobs", "0021_sponsorinquiry")]
    operations = [
        migrations.CreateModel(
            name="Course",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("provider", models.CharField(default="Infinite360 Tech Academy", max_length=120)),
                ("summary", models.TextField(blank=True, help_text="What the course covers, in our own words (2-4 sentences).")),
                ("modules", models.TextField(blank=True, help_text="One topic per line.")),
                ("price_inr", models.PositiveIntegerField(blank=True, null=True, help_text="Price in rupees (e.g. 30000).")),
                ("duration", models.CharField(blank=True, max_length=80, help_text='e.g. "8 weeks" or "40 hours"')),
                ("format", models.CharField(blank=True, max_length=120, help_text='e.g. "Recorded videos + live projects"')),
                ("url", models.URLField(max_length=500, help_text="The course page on the partner's site.")),
                ("coupon_code", models.CharField(blank=True, max_length=40, help_text="Our discount/referral code, e.g. MTJ10.")),
                ("coupon_note", models.CharField(blank=True, max_length=120, help_text='e.g. "10% off for MarTechJobs readers"')),
                ("is_active", models.BooleanField(default=False, help_text="Tick when the details are confirmed with the partner.")),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("clicks", models.PositiveIntegerField(default=0, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tool", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="courses", to="jobs.tool", help_text="The platform this course teaches; links it to that tool's job page.")),
            ],
            options={"ordering": ["sort_order", "title"]},
        ),
    ]
