"""Search Console (Sep 2026): /blog/martech-job-titles-career-paths/ had 12,869
impressions at position 7.8 but a 0.3% click rate. New snippet keeps the
"classification" wording people search for and says what the page contains."""
from django.db import migrations

SLUG = "martech-job-titles-career-paths"
META_TITLE = "MarTech Job Titles Classification (2026): Roles, Levels & Career Paths"
META_DESC = ("How MarTech job titles are classified: Marketing Ops, marketing automation, analytics, "
             "CDP and engineering roles, from entry level to leadership, and what each one does.")


def forwards(apps, schema_editor):
    BlogPost = apps.get_model("jobs", "BlogPost")
    BlogPost.objects.filter(slug=SLUG).update(meta_title=META_TITLE, meta_description=META_DESC)


class Migration(migrations.Migration):
    dependencies = [("jobs", "0018_job_source_key_last_seen")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
