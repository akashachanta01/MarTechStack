"""Search Console (Oct 4 - Oct 31 2026): the HubSpot vs Marketo vs SFMC article ranks
5.7 for 'hubspot marketing hub vs marketo engage vs salesforce marketing cloud' with 0 clicks
from 39 impressions; its title used the abbreviation 'SFMC' and no product names people
search. New title mirrors the query; description cites our real Nov 1 2026 job count."""
from django.db import migrations

SLUG = "hubspot-vs-marketo-vs-salesforce-marketing-cloud"
TITLE = "HubSpot vs Marketo Engage vs Salesforce Marketing Cloud (2026)"
DESC = ("Marketing Hub, Marketo Engage or SFMC? Who uses each, the skills employers ask for, "
        "and live demand: SFMC was named in 127 open roles in Nov 2026.")


def forwards(apps, schema_editor):
    apps.get_model("jobs", "BlogPost").objects.filter(slug=SLUG).update(meta_title=TITLE, meta_description=DESC)


class Migration(migrations.Migration):
    dependencies = [("jobs", "0031_blog_surveys_vs_job_postings")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
