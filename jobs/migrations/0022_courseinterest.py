from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0021_sponsorinquiry"),
    ]

    operations = [
        migrations.CreateModel(
            name="CourseInterest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("program", models.CharField(choices=[("foundation", "Foundation + Advanced MarTech Architecture (recorded) - Rs 60,000"), ("cxo", "CXO Hive - Executive & Architecture Program (live) - Rs 1,00,000"), ("custom", "Live customised program - Rs 1,00,000"), ("cheaper", "A shorter, lower-priced course would suit me better")], default="foundation", max_length=20)),
                ("tool_note", models.CharField(blank=True, max_length=200)),
                ("source_page", models.CharField(blank=True, max_length=300)),
                ("handled", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"verbose_name_plural": "Course interest", "ordering": ["-created_at"]},
        ),
    ]
