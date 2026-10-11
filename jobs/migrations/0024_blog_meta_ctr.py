"""Rewrite titles/descriptions of two blog posts that Google shows a lot but
almost nobody clicks (Search Console, Sept 13 - Oct 11 2026: the job-titles
guide had 5,260 impressions at position 6.9 but a 0.44% click rate)."""
from django.db import migrations

UPDATES = {
    "martech-job-titles-career-paths": (
        "MarTech Job Titles 2026: Every Role Explained + Career Paths",
        "Marketing Ops, marketing automation, analytics, CDP and MarTech engineering titles "
        "explained: what each role does, seniority levels, and where each career path leads.",
    ),
    "martech-jobs": (
        "MarTech Specialist: What the Job Is, Skills & Salary (2026)",
        "What a MarTech Specialist actually does day to day, the platforms employers ask for, "
        "salary expectations and how to get hired.",
    ),
}


def forwards(apps, schema_editor):
    BlogPost = apps.get_model("jobs", "BlogPost")
    for slug, (title, desc) in UPDATES.items():
        BlogPost.objects.filter(slug=slug).update(meta_title=title, meta_description=desc)


class Migration(migrations.Migration):
    dependencies = [("jobs", "0023_courseinterest_user")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
