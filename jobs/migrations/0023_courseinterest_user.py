import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("jobs", "0022_courseinterest"),
    ]

    operations = [
        migrations.AddField(
            model_name="courseinterest",
            name="user",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="course_interests", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name="courseinterest",
            name="program",
            field=models.CharField(choices=[("foundation", "Foundation + Advanced MarTech Architecture (recorded) - Rs 60,000"), ("cxo", "CXO Hive - Executive & Architecture Program (live) - Rs 1,00,000"), ("custom", "Live customised program - Rs 1,00,000"), ("cheaper", "A shorter, lower-priced course would suit me better"), ("other", "A course on another platform")], default="foundation", max_length=20),
        ),
    ]
