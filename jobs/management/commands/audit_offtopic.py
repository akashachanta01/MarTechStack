"""
Audit live jobs for non-MarTech roles that leaked through the screener during
the buggy period (e.g. the 'aep' = Accredited Exercise Physiologist false match).

Flags any active+approved job whose title contains an obviously off-topic term
from healthcare, trades, hospitality, etc. — domains that have nothing to do with
marketing technology. Dry run by default; --confirm deactivates the matches.

  python manage.py audit_offtopic              # list suspects (dry run)
  python manage.py audit_offtopic --confirm    # deactivate + reject them
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from jobs.models import Job

# Terms that should never appear in a legit MarTech job title. Kept narrow and
# unambiguous to avoid nuking real roles (e.g. we DON'T list "nurse" inside a
# longer word, and we avoid generic words like "manager"/"analyst").
OFFTOPIC_TERMS = [
    # Healthcare / allied health (the 'aep' bug class)
    "physiotherapist", "physiotherapy", "occupational therapist",
    "exercise physiologist", "rehabilitation consultant", "registered nurse",
    "speech pathologist", "dietitian", "podiatrist", "psychologist",
    "phlebotomist", "radiographer", "sonographer", "pharmacist",
    "dental", "veterinary", "caregiver", "support worker", "midwife",
    # Trades / manual
    "electrician", "plumber", "carpenter", "welder", "forklift",
    "truck driver", "diesel mechanic", "hvac technician",
    # Hospitality / retail / food
    "barista", "chef", "line cook", "dishwasher", "housekeeping",
    "bartender", "waitress", "waiter", "cashier",
    # Other clearly non-MarTech
    "security guard", "warehouse associate", "flight attendant",
    "teacher aide", "childcare", "social worker",
]


class Command(BaseCommand):
    help = "Find (and optionally deactivate) live non-MarTech jobs that leaked through screening."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", help="Actually deactivate matches (default is a dry run).")

    def handle(self, *args, **options):
        confirm = options["confirm"]

        q = Q()
        for term in OFFTOPIC_TERMS:
            q |= Q(title__icontains=term)

        suspects = list(
            Job.objects.filter(is_active=True, screening_status="approved")
            .filter(q)
            .order_by("company", "title")
        )

        if not suspects:
            self.stdout.write(self.style.SUCCESS("✨ No off-topic live jobs found. Clean."))
            return

        self.stdout.write(f"Found {len(suspects)} suspected off-topic live jobs:\n")
        for j in suspects:
            self.stdout.write(f"  [{j.id}] {j.title}  @  {j.company}  (score {int(j.screening_score)})")

        if not confirm:
            self.stdout.write(self.style.WARNING(
                f"\nDry run. Review the list above, then re-run with --confirm to deactivate {len(suspects)} jobs."
            ))
            return

        ids = [j.id for j in suspects]
        n = Job.objects.filter(id__in=ids).update(
            is_active=False, screening_status="rejected", screening_score=0,
        )
        self.stdout.write(self.style.SUCCESS(f"\n✅ Deactivated {n} off-topic jobs."))
