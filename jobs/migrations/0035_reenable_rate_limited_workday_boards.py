"""Re-enable Workday boards that were switched off during the Nov 2026 rate-limit days.

From about Nov 13 2026 Workday answered our morning requests with HTTP 429 on some
days. A board we could not read was counted as an "empty" board, and after 5 such
days it was auto-disabled (Nasdaq, RSM, Axos and others), so its jobs stopped being
refreshed. fetch_jobs no longer counts a failed poll as empty; this puts the boards
back and clears the false "empty" counts on the boards still enabled.

A board that really has no MarTech roles simply gets disabled again after 5 genuinely
empty polls, so re-enabling is safe. Idempotent. Uses only fields from migration 0008."""
import datetime

from django.db import migrations

FIELDS_USED = ("ats_type", "enabled", "last_polled_at", "consecutive_empty")
SINCE = datetime.datetime(2026, 11, 13, tzinfo=datetime.timezone.utc)


def forwards(apps, schema_editor):
    CompanySource = apps.get_model("jobs", "CompanySource")
    CompanySource.objects.filter(ats_type="workday", enabled=False, last_polled_at__gte=SINCE).update(
        enabled=True, consecutive_empty=0)
    CompanySource.objects.filter(ats_type="workday", enabled=True, consecutive_empty__gt=0).update(
        consecutive_empty=0)


class Migration(migrations.Migration):
    dependencies = [("jobs", "0034_approve_kalsec_submission")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
