"""Approve the Kalsec, Inc. job submitted on Nov 4 2026 (held by the auto-check).

Reviewed by hand: Kalsec is a real company (Kalamazoo, MI), the poster's email is on
kalsec.com, the apply link is Kalsec's own UKG/UltiPro careers board, and the role owns
marketing automation, CRM alignment, analytics and the website (MarTech-relevant).
The auto-check held it only because the title has no MarTech keyword and the careers
site could not be read. Also fixes the logo, which pointed at an unrelated domain.

Idempotent: only touches the row while it is still pending."""
from django.db import migrations
from django.utils import timezone

# Prod's migration history is behind its real schema (the historical Job model has no
# 'slug'), so only fields known to the historical model are used here.
COMPANY = "Kalsec, Inc."
TITLE = "Senior Digital Marketing Manager"
FIELDS_USED = ("company", "title", "poster_email", "screening_status", "is_active", "went_live_at",
               "screened_at", "screening_reason", "screening_details", "company_logo")
POSTER = "kstrohm@kalsec.com"
LOGO = "https://www.google.com/s2/favicons?domain=kalsec.com&sz=128"


def forwards(apps, schema_editor):
    Job = apps.get_model("jobs", "Job")
    job = Job.objects.filter(company=COMPANY, title=TITLE, poster_email__iexact=POSTER,
                             screening_status="pending").first()
    if not job:
        return
    details = dict(job.screening_details or {})
    details["manual_review"] = {
        "at": timezone.now().isoformat(),
        "decision": "approved",
        "why": "Real employer; poster email on kalsec.com; apply link is Kalsec's UKG careers board; "
               "role owns marketing automation, CRM, analytics and website.",
    }
    job.screening_status = "approved"
    job.is_active = True
    job.went_live_at = job.went_live_at or timezone.now()
    job.screened_at = timezone.now()
    job.screening_reason = "Approved after manual review"
    job.screening_details = details
    job.company_logo = LOGO
    job.save(update_fields=["screening_status", "is_active", "went_live_at", "screened_at",
                            "screening_reason", "screening_details", "company_logo"])


class Migration(migrations.Migration):
    dependencies = [("jobs", "0033_never_email_founder_personal")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
