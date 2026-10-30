"""Search Console (Sep 28 - Oct 26 2026): /blog/hubspot-vs-salesforce-which-to-learn/
was shown 202 times at average position 4.9 and got 0 clicks. Rewrite the
headline and description Google shows so they promise the answer searchers want."""
from django.db import migrations

SLUG = "hubspot-vs-salesforce-which-to-learn"
TITLE = "HubSpot vs Salesforce: Which Should You Learn First? (2026)"
DESC = (
    "HubSpot is faster to learn; Salesforce goes deeper and dominates the enterprise. "
    "Compare learning curve, the jobs each leads to and which fits your goals."
)


def forwards(apps, schema_editor):
    BlogPost = apps.get_model("jobs", "BlogPost")
    BlogPost.objects.filter(slug=SLUG).update(meta_title=TITLE, meta_description=DESC)


class Migration(migrations.Migration):
    dependencies = [("jobs", "0028_job_poster_contact")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
