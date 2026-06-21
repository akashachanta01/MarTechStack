"""
Seed the CompanySource registry with curated INTERNATIONAL MarTech employers,
so daily `fetch_jobs --sources-only` polls them in full (free) instead of
waiting for SERP discovery to maybe surface them.

Two buckets per market:
  - MarTech vendor regional offices (reliably hire Marketing Ops / MarTech).
  - Large local employers on public ATS that run real MarTech functions.

IMPORTANT: every candidate is VALIDATED against the live ATS public API before
it's inserted. Token guesses that don't resolve (or boards with zero postings)
are skipped — we never pollute the registry with dead boards. The screener
still decides which individual roles are MarTech; this only adds the boards.

  python manage.py seed_intl_sources             # dry run (validates, no writes)
  python manage.py seed_intl_sources --confirm   # insert the boards that resolve
  python manage.py seed_intl_sources --no-verify --confirm   # skip live checks

Idempotent: existing (ats_type, token) rows are left untouched.
"""

import requests
from django.core.management.base import BaseCommand
from jobs.models import CompanySource

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# (display name, country, ats_type, [candidate tokens]). Multiple tokens are
# tried in order; the first that resolves with live postings is used. Workday
# is intentionally excluded (needs a full tenant URL — too fragile to guess).
CANDIDATES = [
    # --- MarTech vendors (global; regional offices feed UK/EU/IN/SG/AU pages) ---
    ("Braze", "global", "greenhouse", ["braze"]),
    ("Klaviyo", "global", "greenhouse", ["klaviyo"]),
    ("Amplitude", "global", "greenhouse", ["amplitude"]),
    ("Twilio", "global", "greenhouse", ["twilio"]),
    ("Iterable", "global", "greenhouse", ["iterable"]),
    ("mParticle", "global", "greenhouse", ["mparticle"]),
    ("Pendo", "global", "greenhouse", ["pendo"]),
    ("Contentsquare", "france", "greenhouse", ["contentsquare"]),
    ("Optimizely", "global", "greenhouse", ["optimizely"]),
    ("CleverTap", "india", "lever", ["clevertap"]),
    ("MoEngage", "india", "lever", ["moengage"]),

    # --- United Kingdom ---
    ("Monzo", "united-kingdom", "greenhouse", ["monzo"]),
    ("Wise", "united-kingdom", "greenhouse", ["wise", "transferwise", "wisejobs"]),
    ("Deliveroo", "united-kingdom", "greenhouse", ["deliveroo"]),
    ("GoCardless", "united-kingdom", "greenhouse", ["gocardless"]),
    ("Checkout.com", "united-kingdom", "greenhouse", ["checkoutcom", "checkout-com"]),
    ("Trainline", "united-kingdom", "smartrecruiters", ["Trainline"]),

    # --- India ---
    ("Freshworks", "india", "greenhouse", ["freshworks", "freshdesk"]),
    ("Razorpay", "india", "greenhouse", ["razorpaysoftwareprivatelimited", "razorpay"]),
    ("Postman", "india", "greenhouse", ["postman"]),
    ("Chargebee", "india", "lever", ["chargebee"]),
    ("CleverTap", "india", "greenhouse", ["clevertap"]),
    ("MoEngage", "india", "greenhouse", ["moengage"]),
    ("Hasura", "india", "greenhouse", ["hasura"]),
    ("Zoho", "india", "greenhouse", ["zoho"]),
    # HubSpot India office — same board as global but filters to India locations
    ("HubSpot", "india", "greenhouse", ["hubspot"]),

    # --- Singapore ---
    ("Nium", "singapore", "lever", ["nium"]),
    ("Carousell", "singapore", "smartrecruiters", ["carousellgroup", "carousell"]),
    ("Zendesk APAC", "singapore", "greenhouse", ["zendesk"]),
    ("Intercom", "singapore", "greenhouse", ["intercom"]),

    # --- Germany ---
    ("Delivery Hero", "germany", "greenhouse", ["deliveryhero", "delivery-hero"]),
    ("N26", "germany", "greenhouse", ["n26"]),
    ("Personio", "germany", "greenhouse", ["personio"]),
    ("Celonis", "germany", "greenhouse", ["celonis"]),
    ("HelloFresh", "germany", "greenhouse", ["4lu44n1n37w012k", "hellofresh"]),

    # --- France ---
    ("Dataiku", "france", "greenhouse", ["dataiku"]),
    ("Back Market", "france", "ashby", ["backmarket"]),
    ("Mirakl", "france", "greenhouse", ["mirakl"]),
    ("Mirakl (Workable)", "france", "workable", ["mirakl-careers"]),

    # --- Netherlands ---
    ("Adyen", "netherlands", "greenhouse", ["adyen"]),
    ("Mollie", "netherlands", "ashby", ["mollie"]),
    ("Bird (MessageBird)", "netherlands", "greenhouse", ["messagebird", "bird"]),

    # --- Canada ---
    ("Lightspeed", "canada", "lever", ["lightspeed", "lightspeedhq"]),
    ("Wealthsimple", "canada", "lever", ["wealthsimple"]),
    ("Wealthsimple (Ashby)", "canada", "ashby", ["wealthsimple"]),
    ("1Password", "canada", "lever", ["1password"]),
    ("1Password (Ashby)", "canada", "ashby", ["1password"]),
    ("Hootsuite", "canada", "greenhouse", ["hootsuite"]),
    ("Shopify", "canada", "greenhouse", ["shopify"]),

    # --- UAE ---
    ("Careem", "united-arab-emirates", "greenhouse", ["careem"]),
    ("Kitopi", "united-arab-emirates", "greenhouse", ["kitopi"]),
    ("Tabby", "united-arab-emirates", "greenhouse", ["tabby", "tabby-ae"]),

    # --- Australia ---
    ("Canva", "australia", "smartrecruiters", ["Canva", "canva"]),
    ("Airwallex", "australia", "lever", ["airwallex"]),
    ("Airwallex (Ashby)", "australia", "ashby", ["airwallex"]),
    ("SafetyCulture", "australia", "greenhouse", ["safetyculture", "safety-culture"]),
    ("Atlassian", "australia", "greenhouse", ["atlassian"]),
]


def _count_greenhouse(token):
    r = requests.get(
        f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
        headers=_HEADERS, timeout=8,
    )
    return len(r.json().get("jobs", [])) if r.status_code == 200 else None


def _count_lever(token):
    r = requests.get(
        f"https://api.lever.co/v0/postings/{token}?mode=json",
        headers=_HEADERS, timeout=8,
    )
    return len(r.json()) if r.status_code == 200 and isinstance(r.json(), list) else None


def _count_ashby(token):
    r = requests.post(
        f"https://api.ashbyhq.com/posting-api/job-board/{token}",
        headers=_HEADERS, timeout=8,
    )
    return len(r.json().get("jobs", [])) if r.status_code == 200 else None


def _count_smartrecruiters(token):
    r = requests.get(
        f"https://api.smartrecruiters.com/v1/companies/{token}/postings",
        headers=_HEADERS, timeout=8,
    )
    return len(r.json().get("content", [])) if r.status_code == 200 else None


def _count_recruitee(token):
    r = requests.get(
        f"https://{token}.recruitee.com/api/offers/", headers=_HEADERS, timeout=8,
    )
    return len(r.json().get("offers", [])) if r.status_code == 200 else None


def _count_workable(token):
    r = requests.get(
        f"https://apply.workable.com/api/v1/widget/accounts/{token}",
        headers=_HEADERS, timeout=8,
    )
    return len(r.json().get("jobs", [])) if r.status_code == 200 else None


_VALIDATORS = {
    "greenhouse": _count_greenhouse,
    "lever": _count_lever,
    "ashby": _count_ashby,
    "smartrecruiters": _count_smartrecruiters,
    "recruitee": _count_recruitee,
    "workable": _count_workable,
}


class Command(BaseCommand):
    help = "Seed CompanySource with curated international MarTech employers (validated)."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", help="Actually create rows.")
        parser.add_argument("--no-verify", action="store_true", help="Skip live ATS validation.")

    def handle(self, *args, **options):
        confirm = options["confirm"]
        verify = not options["no_verify"]

        existing = set(CompanySource.objects.values_list("ats_type", "token"))
        to_create = []   # (name, country, ats_type, token, postings)
        skipped = []     # (name, reason)

        for name, country, ats_type, tokens in CANDIDATES:
            resolved = None
            for token in tokens:
                if (ats_type, token) in existing:
                    skipped.append((name, f"already registered ({ats_type}:{token})"))
                    resolved = "exists"
                    break
                if not verify:
                    resolved = (token, None)
                    break
                validator = _VALIDATORS.get(ats_type)
                if not validator:
                    continue
                try:
                    n = validator(token)
                except Exception as e:
                    self.stdout.write(f"   … {name} [{ats_type}:{token}] check failed: {e}")
                    n = None
                if n is not None and n > 0:
                    resolved = (token, n)
                    break
            if resolved == "exists":
                continue
            if not resolved:
                skipped.append((name, "no token resolved with live postings"))
                continue
            token, postings = resolved
            to_create.append((name, country, ats_type, token, postings))
            pc = f"{postings} postings" if postings is not None else "unverified"
            self.stdout.write(self.style.SUCCESS(f"   ✓ {name} [{ats_type}:{token}] — {pc}"))

        # Per-country summary so we can see which markets actually have supply.
        by_country = {}
        for name, country, ats_type, token, postings in to_create:
            by_country.setdefault(country, 0)
            by_country[country] += 1
        self.stdout.write("\n📊 Boards that resolved, by market:")
        for country in sorted(by_country):
            self.stdout.write(f"   {country}: {by_country[country]}")
        self.stdout.write(f"\n   Total new boards: {len(to_create)} | skipped: {len(skipped)}")
        if skipped:
            self.stdout.write("   Skipped:")
            for name, reason in skipped:
                self.stdout.write(f"     - {name}: {reason}")

        if not to_create:
            self.stdout.write(self.style.WARNING("Nothing new to add."))
            return
        if not confirm:
            self.stdout.write(self.style.WARNING(
                f"\nDry run. Re-run with --confirm to create {len(to_create)} sources."))
            return

        created = 0
        for name, country, ats_type, token, postings in to_create:
            _, was_created = CompanySource.objects.get_or_create(
                ats_type=ats_type, token=token,
                defaults={"name": name, "notes": f"intl seed: {country}"},
            )
            created += 1 if was_created else 0
        self.stdout.write(self.style.SUCCESS(f"\n✨ Created {created} international company sources."))
