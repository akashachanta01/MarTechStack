import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

PROGRAM_CHOICES = [("foundation", "Foundation + Advanced MarTech Architecture (recorded) - Rs 60,000"), ("cxo", "CXO Hive - Executive & Architecture Program (live) - Rs 1,00,000"), ("custom", "Live customised program - Rs 1,00,000"), ("cheaper", "A shorter, lower-priced course would suit me better"), ("other", "A course on another platform"), ("course", "This course")]

SEED = [
    dict(slug="adobe-aep-ajo-cja", order=1, color="navy", badge="Start here",
         title="Adobe AEP, Journey Optimizer & CJA: Foundation + Advanced Architecture",
         subtitle="Learn Adobe Experience Platform, Journey Optimizer and Customer Journey Analytics, then the MarTech and CDP architecture behind enterprise implementations.",
         platform="Adobe Experience Cloud", level="intermediate", format="recorded", format_note="Learn at your own pace",
         price_inr=60000, price_usd=625,
         learn="Adobe Experience Platform (AEP)\nAdobe Journey Optimizer (AJO)\nCustomer Journey Analytics (CJA)\nDigital and MarTech architecture\nEnterprise implementation patterns\nCustomer Data Platform architecture\nAI and data-driven customer experience",
         curriculum="## Foundation MarTech Series\nAdobe Experience Platform (AEP)\nAdobe Journey Optimizer (AJO)\nCustomer Journey Analytics (CJA)\n## Advanced Digital Architecture Program\nDigital and MarTech architecture\nEnterprise implementation patterns\nCustomer Data Platform architecture\nAI and data-driven customer experience",
         includes="Recorded video lessons\nTest series\nERD resources\nE-library\nAdditional learning material",
         for_whom="People who want to work on Adobe Experience Platform, Journey Optimizer or CJA projects\nMarketing ops and MarTech engineers moving into the Adobe stack",
         tool_slugs="adobe-experience-platform,adobe-journey-optimizer,customer-journey-analytics"),
    dict(slug="cxo-hive-executive-architecture", order=2, color="violet", badge="For leaders",
         title="CXO Hive: Executive & Architecture Program",
         subtitle="For leaders and enterprise architects setting up MarTech and AI capability at scale.",
         platform="MarTech leadership", level="leaders", format="live", format_note="1 month of post-program support",
         price_inr=100000, price_usd=1041,
         learn="Setting up a MarTech / AI Center of Excellence\nGCC-to-global capability transformation\nAI and agentic AI strategy\nCustomer Data Platform strategy\nEnterprise architecture and governance\nBuilding reusable capabilities and global delivery models",
         curriculum="## Strategy\nSetting up a MarTech / AI Center of Excellence\nAI and agentic AI strategy\nCustomer Data Platform strategy\n## Architecture and delivery\nEnterprise architecture and governance\nGCC-to-global capability transformation\nBuilding reusable capabilities and global delivery models",
         includes="Live sessions\n1 month of post-program support",
         for_whom="CXOs and C-level executives\nTechnology leaders\nEnterprise architects",
         tool_slugs="adobe-experience-platform"),
    dict(slug="live-customised-martech-program", order=3, color="green", badge="Tailored",
         title="Live Customised MarTech Program",
         subtitle="A live program built around your role, your business requirements and your technology landscape.",
         platform="Any MarTech stack", level="all", format="live", format_note="For individuals or teams",
         price_inr=100000, price_usd=1041, price_note="per program",
         learn="Content built around your role\nFitted to your business requirements\nMatched to your technology landscape",
         curriculum="", includes="Live sessions\nContent customised to you or your team",
         for_whom="Organizations training a team\nIndividuals who want a program fitted to their role",
         tool_slugs=""),
]


def seed(apps, schema_editor):
    Course = apps.get_model("jobs", "Course")
    for row in SEED:
        Course.objects.update_or_create(slug=row["slug"], defaults=row)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("jobs", "0022_courseinterest"),
    ]

    operations = [
        migrations.CreateModel(
            name="Course",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(unique=True)),
                ("title", models.CharField(max_length=200)),
                ("subtitle", models.CharField(blank=True, max_length=300)),
                ("platform", models.CharField(help_text="Shown on the card, e.g. 'Adobe Experience Cloud'", max_length=100)),
                ("level", models.CharField(choices=[("beginner", "Beginner"), ("intermediate", "Intermediate"), ("advanced", "Advanced"), ("leaders", "Leaders & architects"), ("all", "All levels")], default="all", max_length=20)),
                ("format", models.CharField(choices=[("recorded", "Recorded"), ("live", "Live"), ("hybrid", "Recorded + live")], default="recorded", max_length=20)),
                ("format_note", models.CharField(blank=True, help_text="e.g. '1 month support after'", max_length=120)),
                ("badge", models.CharField(blank=True, help_text="Optional tag, e.g. 'Start here'", max_length=40)),
                ("color", models.CharField(choices=[("navy", "Navy"), ("amber", "Amber"), ("violet", "Violet"), ("green", "Green")], default="navy", max_length=10)),
                ("price_inr", models.PositiveIntegerField(help_text="Full price in rupees")),
                ("price_usd", models.PositiveIntegerField(help_text="Full price in US dollars")),
                ("price_note", models.CharField(default="one-time", max_length=40)),
                ("member_discount_pct", models.PositiveSmallIntegerField(default=0, help_text="Discount for signed-in members, agreed with the course partner. 0 = none.")),
                ("learn", models.TextField(blank=True, help_text="What you'll learn: one point per line")),
                ("curriculum", models.TextField(blank=True, help_text="Course content: '## Section' lines, then one topic per line")),
                ("includes", models.TextField(blank=True, help_text="This course includes: one item per line")),
                ("for_whom", models.TextField(blank=True, help_text="Who this course is for: one point per line")),
                ("tool_slugs", models.CharField(blank=True, help_text="Comma-separated tool slugs for live job demand", max_length=300)),
                ("is_active", models.BooleanField(default=True)),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["order", "id"]},
        ),
        migrations.AddField(
            model_name="courseinterest",
            name="user",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="course_interests", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="courseinterest",
            name="course",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="interests", to="jobs.course"),
        ),
        migrations.AlterField(
            model_name="courseinterest",
            name="program",
            field=models.CharField(choices=PROGRAM_CHOICES, default="foundation", max_length=20),
        ),
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
