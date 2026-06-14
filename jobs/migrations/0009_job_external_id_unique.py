# Hand-written (audit follow-up). Add a PARTIAL unique index on Job.external_id
# so two overlapping fetch runs can't create duplicate live jobs (each duplicate
# is also a wasted paid GPT call). The index is partial (external_id <> '') so the
# many legacy rows with an empty external_id are unaffected.
#
# A RunPython step first removes any pre-existing duplicate external_ids (keeping
# the oldest row) so AddConstraint can't fail on a production DB that already
# contains duplicates.

from django.db import migrations, models
from django.db.models import Q


def dedupe_external_ids(apps, schema_editor):
    Job = apps.get_model("jobs", "Job")
    seen = set()
    # Oldest first — keep the original, drop later duplicates.
    qs = (Job.objects.exclude(external_id="")
          .order_by("id").values_list("id", "external_id"))
    dupe_ids = []
    for job_id, ext in qs.iterator():
        if ext in seen:
            dupe_ids.append(job_id)
        else:
            seen.add(ext)
    if dupe_ids:
        Job.objects.filter(id__in=dupe_ids).delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0008_companysource_job_ingestion_fields"),
    ]

    operations = [
        migrations.RunPython(dedupe_external_ids, noop),
        migrations.AddConstraint(
            model_name="job",
            constraint=models.UniqueConstraint(
                fields=["external_id"],
                condition=Q(external_id__gt=""),
                name="jobs_job_external_id_uniq",
            ),
        ),
    ]
