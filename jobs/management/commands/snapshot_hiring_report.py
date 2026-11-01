"""Save this month's MarTech Hiring Report numbers (daily cron; last run of the month wins)."""
import json

from django.core.cache import cache
from django.core.management.base import BaseCommand

from jobs.hiring_report import compute_report, month_start
from jobs.models import HiringSnapshot


class Command(BaseCommand):
    help = "Save the current month's hiring report numbers for month-over-month comparisons."

    def handle(self, *args, **opts):
        data = json.loads(json.dumps(compute_report(), default=str))
        snap, _ = HiringSnapshot.objects.update_or_create(month=month_start(), defaults={"data": data})
        cache.delete("market_stats_v2")
        self.stdout.write(self.style.SUCCESS(f"📊 Hiring report snapshot {snap.month:%B %Y}: {data['total']} live jobs."))
