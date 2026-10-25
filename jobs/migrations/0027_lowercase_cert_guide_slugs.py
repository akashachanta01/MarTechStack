"""Certification guide slugs must be lowercase: the view 301s any uppercase URL to
lowercase, so the 'Salesforce' guide (/Salesforce-certification/) was unreachable
(404 in prod logs, Oct 2026). Skips a guide if a lowercase twin already exists."""
from django.db import migrations


def forwards(apps, schema_editor):
    Guide = apps.get_model("jobs", "CertificationGuide")
    for g in Guide.objects.all():
        low = g.slug.lower()
        if g.slug != low and not Guide.objects.filter(slug=low).exists():
            g.slug = low
            g.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [("jobs", "0026_job_titles_taxonomy_table")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
