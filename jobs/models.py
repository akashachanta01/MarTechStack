from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth.models import User
import html
import bleach
from bs4 import BeautifulSoup
import re
from datetime import timedelta

# --- HELPER 1: LOCATION STANDARDIZER ---
def normalize_location(loc):
    if not loc: return "Remote"
    cleaned = loc.strip().replace(" - ", ", ").replace(" | ", ", ").replace("/", ", ")
    state_map = {
        "California": "CA", "New York": "NY", "Texas": "TX", "Washington": "WA",
        "Illinois": "IL", "Massachusetts": "MA", "Georgia": "GA", "Colorado": "CO",
        "Florida": "FL", "Virginia": "VA", "Pennsylvania": "PA", "Ohio": "OH",
        "North Carolina": "NC", "Michigan": "MI", "Arizona": "AZ", "New Jersey": "NJ"
    }
    for state, code in state_map.items():
        if f", {state}" in cleaned:
            cleaned = cleaned.replace(f", {state}", f", {code}")
    lower_loc = cleaned.lower()
    city_map = {
        "new york": "New York, NY, United States",
        "nyc": "New York, NY, United States",
        "san francisco": "San Francisco, CA, United States",
        "sf": "San Francisco, CA, United States",
        "los angeles": "Los Angeles, CA, United States",
        "london": "London, United Kingdom",
        "bengaluru": "Bengaluru, India",
        "bangalore": "Bengaluru, India",
        "toronto": "Toronto, ON, Canada",
        "vancouver": "Vancouver, BC, Canada",
        "sydney": "Sydney, Australia",
        "remote": "Remote",
    }
    if lower_loc in city_map: return city_map[lower_loc]
    if "United States" not in cleaned and "Remote" not in cleaned:
        if re.search(r', [A-Z]{2}$', cleaned): cleaned += ", United States"
    return cleaned

# --- HELPER 2: DESCRIPTION CLEANER ---
# Allowlist sanitization with bleach. Anything not explicitly permitted is
# stripped, so hostile markup from ATS feeds (script/onclick/style/etc.) can
# never reach the rendered page — far safer than the old blocklist.
ALLOWED_TAGS = ['p', 'br', 'ul', 'ol', 'li', 'strong', 'em', 'b', 'i',
                'h2', 'h3', 'h4', 'a', 'span', 'div', 'table', 'thead',
                'tbody', 'tr', 'th', 'td']
ALLOWED_ATTRS = {'a': ['href', 'title'], 'span': ['class'], 'div': ['class']}

def clean_html_description(text):
    if not text: return ""
    text = html.unescape(text)
    clean_text = bleach.clean(text, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
    return re.sub(r'\n\s*\n', '\n\n', clean_text).strip()

# --- MODELS ---

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    def __str__(self): return self.name
    class Meta: verbose_name_plural = "Categories"

class Tool(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="tools")
    
    # SEO Fields
    logo_url = models.URLField(max_length=500, blank=True, null=True, help_text="Official logo of the tool")
    description = models.TextField(blank=True, default="", help_text="SEO Content: Appears at top of page.")
    seo_title = models.CharField(max_length=200, blank=True, default="", help_text="Browser Title (e.g. 'HubSpot Jobs & Careers')")
    seo_h1 = models.CharField(max_length=200, blank=True, default="", help_text="Page Heading (e.g. 'Top HubSpot Jobs')")

    def __str__(self): return self.name
    @property
    def color_class(self):
        colors = ['bg-emerald-100 text-emerald-700 border-emerald-200','bg-amber-100 text-amber-800 border-amber-200','bg-rose-100 text-rose-700 border-rose-200','bg-sky-100 text-sky-700 border-sky-200','bg-violet-100 text-violet-700 border-violet-200','bg-indigo-100 text-indigo-700 border-indigo-200']
        return colors[sum(ord(c) for c in self.name) % len(colors)]

class Job(models.Model):
    ROLE_TYPE_CHOICES = [('full_time', 'Full-time'), ('contract', 'Contract'), ('part_time', 'Part-time'), ('temporary', 'Temporary'), ('internship', 'Internship')]
    STATUS_CHOICES = [('pending', 'Pending Review'), ('approved', 'Approved'), ('rejected', 'Rejected')]
    WORK_ARRANGEMENT_CHOICES = [('remote', 'Remote'), ('hybrid', 'Hybrid'), ('onsite', 'On-site')]
    FUNCTION_CHOICES = [('engineering', 'Engineering'), ('operations', 'Operations'), ('data', 'Data'), ('other', 'Other')]

    title = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    company_logo = models.URLField(max_length=500, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField()
    apply_url = models.URLField(max_length=500)
    slug = models.SlugField(max_length=250, null=True, blank=True)
    
    function = models.CharField(max_length=20, choices=FUNCTION_CHOICES, default='other', db_index=True)
    role_type = models.CharField(max_length=20, choices=ROLE_TYPE_CHOICES, default='full_time')
    salary_range = models.CharField(max_length=100, blank=True, null=True)
    work_arrangement = models.CharField(max_length=10, choices=WORK_ARRANGEMENT_CHOICES, default='onsite')
    tools = models.ManyToManyField(Tool, related_name="jobs", blank=True)
    
    screening_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_active = models.BooleanField(default=False)
    screened_at = models.DateTimeField(blank=True, null=True)
    
    screening_score = models.FloatField(blank=True, null=True)
    screening_reason = models.TextField(blank=True, default="")
    screening_details = models.JSONField(blank=True, default=dict)

    is_featured = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    plan_name = models.CharField(max_length=50, blank=True, null=True)
    tags = models.CharField(max_length=200, blank=True, null=True)

    # --- Structured ingestion fields (Sprint 3b) ---
    # ATS-native identity for reliable dedup: "<source>:<native_id>" so the same
    # posting re-seen on a later poll is recognized even if the URL drifts.
    external_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    # Structured location captured at ingest (free-text `location` stays the
    # display value). country is an ISO-2 code; region is a state/province.
    country = models.CharField(max_length=2, blank=True, default="")
    region = models.CharField(max_length=100, blank=True, default="")
    # Remote scope: "" (not remote), "anywhere" (remote, no geo limit), or a
    # country code the remote role is restricted to (e.g. "US"). Lets us serve
    # both "remote anywhere" and "remote in <country>" without parsing text.
    remote_scope = models.CharField(max_length=20, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Set the first time is_active flips to True (auto-approval at ingest or
    # manual admin action). Used by send_daily_digest so it catches jobs
    # approved any time — not just those ingested within the last 24 h.
    went_live_at = models.DateTimeField(null=True, blank=True, db_index=True)
    # Flipped to True once the job has been included in a digest email, so the
    # same role is never re-sent in tomorrow's digest.
    digest_sent = models.BooleanField(default=False, db_index=True)

    def __str__(self): return f"{self.title} at {self.company}"

    def get_salary_min_max(self):
        """Best-effort parse of the free-text salary into annual (min, max).

        Handles k/M suffixes, decimals, comma thousands, and hourly rates
        (annualized at 2080 h/yr). Filters implausible tokens (years, counts)
        so we never publish a fabricated or nonsensical number.
        """
        if not self.salary_range:
            return None, None
        txt = self.salary_range.lower()
        is_hourly = any(h in txt for h in ('/hr', '/hour', 'per hour', 'hourly', 'an hour'))
        try:
            vals = []
            for num_str, suffix in re.findall(r'(\d[\d,]*(?:\.\d+)?)\s*([km])?', txt):
                num = float(num_str.replace(',', ''))
                if suffix == 'k':
                    num *= 1_000
                elif suffix == 'm':
                    num *= 1_000_000
                elif not is_hourly and num < 1000:
                    # bare "150" in a salary range almost always means 150k
                    num *= 1_000
                vals.append(num)
            if is_hourly:
                vals = [v * 2080 for v in vals if 5 <= v <= 1000]
            else:
                vals = [v for v in vals if 10_000 <= v <= 2_000_000]
            if not vals:
                return None, None
            vals.sort()
            return int(vals[0]), int(vals[-1])
        except Exception:
            return None, None

    def get_schema_country(self):
        # ISO country code for Google Jobs structured data. Prefer the
        # structured `country` field captured at ingest (reliable) before
        # falling back to parsing free-text location. Without this, jobs in
        # "London, UK" / "Shanghai, China" / "Dubai, UAE" fell through to the
        # US default and were mislabeled in Google for Jobs.
        if self.country:
            return self.country
        loc = (self.location or "").lower()
        country_map = {
            "united kingdom": "GB", "england": "GB", "scotland": "GB",
            "wales": "GB", ", uk": "GB", "london": "GB",
            "india": "IN", "bengaluru": "IN", "bangalore": "IN", "mumbai": "IN",
            "chennai": "IN", "hyderabad": "IN", "pune": "IN", "gurgaon": "IN",
            "gurugram": "IN", "noida": "IN", "delhi": "IN",
            "canada": "CA", "australia": "AU", "germany": "DE", "france": "FR",
            "netherlands": "NL", "ireland": "IE", "spain": "ES",
            "singapore": "SG", "mexico": "MX", "brazil": "BR",
            "china": "CN", "shanghai": "CN", "beijing": "CN", "shenzhen": "CN",
            "hong kong": "HK",
            "united arab emirates": "AE", "uae": "AE", "dubai": "AE",
            "abu dhabi": "AE",
        }
        for name, code in country_map.items():
            if name in loc:
                return code
        return "US"

    # Country names we strip off the end of a location string when parsing
    # the city/region for JobPosting schema.
    _COUNTRY_NAMES = {
        "united states", "usa", "u.s.", "u.s.a.", "us", "united kingdom", "uk",
        "u.k.", "canada", "australia", "germany", "france", "netherlands",
        "ireland", "spain", "singapore", "mexico", "brazil", "india",
        "china", "hong kong", "united arab emirates", "uae", "u.a.e.",
    }

    def get_address_parts(self):
        """
        Best-effort split of the free-text location into city/region for
        JobPosting structured data. Returns {} for remote/unknown so we never
        emit a fake "Remote" city. Never fabricates street address or postal code.
        """
        loc = (self.location or "").strip()
        if not loc or any(k in loc.lower() for k in ("remote", "anywhere", "worldwide", "wfh")):
            return {"locality": "", "region": ""}
        parts = [p.strip() for p in loc.split(",") if p.strip()]
        if parts and parts[-1].lower() in self._COUNTRY_NAMES:
            parts = parts[:-1]
        return {
            "locality": parts[0] if parts else "",
            "region": parts[1] if len(parts) > 1 else "",
        }

    # ISO-2 country -> ISO-4217 currency for the JobPosting baseSalary. Lets us
    # stop hardcoding USD, which mislabeled every international salary (a £70k
    # London role was advertised to Google as $70k) and erodes Google for Jobs
    # trust in the structured data.
    _COUNTRY_CURRENCY = {
        "US": "USD", "GB": "GBP", "CA": "CAD", "AU": "AUD", "IN": "INR",
        "SG": "SGD", "DE": "EUR", "FR": "EUR", "NL": "EUR", "IE": "EUR",
        "ES": "EUR", "CN": "CNY", "HK": "HKD", "AE": "AED", "BR": "BRL",
        "MX": "MXN",
    }

    def get_schema_currency(self):
        """ISO-4217 currency for the salary in JobPosting schema. Prefer an
        explicit currency symbol/code in the free-text salary, then the job's
        country, then USD."""
        txt = (self.salary_range or "")
        low = txt.lower()
        symbol_map = {"£": "GBP", "€": "EUR", "₹": "INR", "¥": "CNY",
                      "₩": "KRW", "₪": "ILS"}
        for sym, code in symbol_map.items():
            if sym in txt:
                return code
        # Explicit 3-letter codes occasionally present in ATS salary strings.
        for code in ("gbp", "eur", "inr", "sgd", "aed", "cad", "aud", "cny",
                     "usd", "hkd", "brl", "mxn"):
            if code in low:
                return code.upper()
        # "S$" Singapore, "A$"/"AU$" Australian, "C$"/"CA$" Canadian, "د.إ" AED.
        if "s$" in low:
            return "SGD"
        if "a$" in low or "au$" in low:
            return "AUD"
        if "c$" in low or "ca$" in low:
            return "CAD"
        return self._COUNTRY_CURRENCY.get(self.get_schema_country(), "USD")

    def get_schema_valid_through(self):
        # Match the real cull window (clean_stale_jobs demotes 60 days after a
        # job GOES LIVE) so Google for Jobs doesn't keep showing "open" roles
        # that then 404. ISO 8601 *datetime* (not date-only): Google for Jobs
        # requires the full timestamp or it can reject the rich result.
        anchor = self.went_live_at or self.created_at
        return (anchor + timedelta(days=60)).strftime('%Y-%m-%dT%H:%M:%S')

    def save(self, *args, **kwargs):
        if self.location: self.location = normalize_location(self.location)
        if self.description: self.description = clean_html_description(self.description)
        if not self.slug: self.slug = slugify(f"{self.title} at {self.company}")
        # Safety: a job that isn't approved can never be visible.
        if self.screening_status != 'approved':
            self.is_active = False
        else:
            # Auto-activate when a job is created approved or its status
            # *transitions* to approved (e.g. inline edits in the admin list).
            # An already-approved job keeps its current is_active, so the
            # admin Hide action sticks.
            old_status = None
            if self.pk:
                old_status = Job.objects.filter(pk=self.pk).values_list('screening_status', flat=True).first()
            if old_status != 'approved':
                self.is_active = True
        # Stamp went_live_at the first time the job becomes active so the daily
        # digest can find it regardless of when it was originally ingested.
        if self.is_active and not self.went_live_at:
            self.went_live_at = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        indexes = [models.Index(fields=['is_active', 'screening_status']), models.Index(fields=['created_at'])]
        constraints = [
            # ATS-native id is globally unique per posting; the partial condition
            # exempts legacy/AI-scraped rows that have no external_id.
            models.UniqueConstraint(
                fields=['external_id'],
                condition=models.Q(external_id__gt=''),
                name='jobs_job_external_id_uniq',
            ),
        ]

class BlogPost(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, help_text="URL friendly version of title")
    excerpt = models.TextField(help_text="Short summary for the blog card (2-3 sentences).")
    content = models.TextField(help_text="Full HTML content of the article.")
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    author = models.CharField(max_length=100, default="MarTechJobs Team")
    category = models.CharField(max_length=50, default="Career Advice")
    read_time = models.CharField(max_length=20, default="5 min read")
    published_at = models.DateField(default=timezone.now)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self): return self.title
    class Meta: ordering = ['-published_at']

class InterviewGuide(models.Model):
    """Per-tool interview guide (e.g. /hubspot-interview-questions/). The
    curated question bank lives here (admin-editable); the page also renders a
    live "data spine" (open roles, co-required tools, hiring companies)
    computed from the job corpus at request time, so it stays fresh."""
    tool = models.OneToOneField('Tool', on_delete=models.CASCADE, related_name='interview_guide')
    slug = models.SlugField(max_length=120, unique=True, help_text="Usually the tool slug, e.g. 'hubspot'.")
    intro = models.TextField(blank=True, help_text="Opening HTML paragraph(s).")
    prep_tips = models.TextField(blank=True, help_text="Optional 'how to prepare' HTML.")
    # [{"category": "...", "items": [{"q": "...", "a": "..."}, ...]}, ...]
    questions = models.JSONField(default=list, blank=True)
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tool.name} interview guide"

    def question_count(self):
        return sum(len(sec.get('items', [])) for sec in (self.questions or []))


class CertificationGuide(models.Model):
    tool = models.OneToOneField('Tool', on_delete=models.CASCADE, related_name='cert_guide')
    slug = models.SlugField(max_length=120, unique=True)
    cert_name = models.CharField(max_length=200)  # e.g. "HubSpot Marketing Hub Certification"
    provider = models.CharField(max_length=100, blank=True)  # e.g. "HubSpot Academy"
    cost = models.CharField(max_length=100, blank=True)  # e.g. "Free"
    exam_format = models.CharField(max_length=200, blank=True)  # e.g. "60 questions, 3 hours, 75% pass mark"
    validity = models.CharField(max_length=100, blank=True)  # e.g. "2 years"
    difficulty = models.CharField(max_length=50, blank=True)  # e.g. "Intermediate"
    intro = models.TextField(blank=True)
    who_should_get = models.TextField(blank=True)
    study_path = models.JSONField(default=list, blank=True)  # [{step, title, desc, hours?}]
    exam_topics = models.JSONField(default=list, blank=True)  # [{topic, weight?, desc?}]
    prep_tips = models.TextField(blank=True)
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.cert_name


class Subscriber(models.Model):
    # A row here = a CONFIRMED newsletter subscriber. New signups land in
    # PendingSubscriber first and are only promoted here after they click the
    # confirmation link (double opt-in).
    #
    # Unsubscribe is a SOFT delete (is_active=False), not a row delete: keeping
    # the row preserves the opt-out record so a stray get_or_create can't
    # silently resurrect a suppressed address, and so all digests filter on
    # is_active=True. Re-subscribing (via the double opt-in flow) reactivates it.
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    def __str__(self): return self.email


class PendingSubscriber(models.Model):
    """Unconfirmed newsletter signup awaiting double opt-in. Promoted to a real
    Subscriber once the emailed confirmation link is clicked."""
    email = models.EmailField(unique=True)
    token = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"pending: {self.email}"

class SavedSearch(models.Model):
    """A targeted job alert: an email + the filters it should match on.

    Created when someone subscribes from a filtered/search context (the
    'Be first to new X roles' bar). New matching jobs are emailed daily via
    send_saved_search_alerts — separate from the general Subscriber digest.
    """
    email = models.EmailField(db_index=True)
    query = models.CharField(max_length=200, blank=True, default="")
    tool = models.CharField(max_length=100, blank=True, default="")        # tool slug
    location = models.CharField(max_length=120, blank=True, default="")
    function = models.CharField(max_length=20, blank=True, default="")     # engineering/operations/data
    arrangement = models.CharField(max_length=20, blank=True, default="")  # remote/hybrid/onsite
    label = models.CharField(max_length=200, blank=True, default="")       # human-readable summary
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Saved searches"
        indexes = [models.Index(fields=["email", "is_active"], name="jobs_ss_email_active_idx")]

    def __str__(self):
        return f"{self.email} · {self.label or 'all MarTech'}"

class CompanySource(models.Model):
    """A known company ATS board to poll directly (Sprint 3b).

    SERP discovery is expensive and only surfaces the top handful of search
    results. Every board that discovery successfully fetches is recorded here,
    so a cheap daily `fetch_jobs --sources-only` run can poll the FULL board
    directly — no search spend, complete coverage. Dead boards auto-disable
    after several consecutive empty polls.
    """
    ATS_CHOICES = [
        ("greenhouse", "Greenhouse"), ("lever", "Lever"), ("ashby", "Ashby"),
        ("workable", "Workable"), ("smartrecruiters", "SmartRecruiters"),
        ("recruitee", "Recruitee"), ("workday", "Workday"),
    ]
    name = models.CharField(max_length=200, help_text="Display company name")
    ats_type = models.CharField(max_length=20, choices=ATS_CHOICES, db_index=True)
    # Board identifier for slug-based ATS (greenhouse token, lever handle, etc.).
    token = models.CharField(max_length=200, blank=True, default="")
    # Full board URL for ATS that need more than a slug (Workday tenant/host/site).
    board_url = models.URLField(max_length=500, blank=True, default="")

    enabled = models.BooleanField(default=True, db_index=True)
    last_polled_at = models.DateTimeField(null=True, blank=True)
    last_seen_count = models.IntegerField(default=0)    # postings returned last poll
    last_added_count = models.IntegerField(default=0)   # net-new approved last poll
    consecutive_empty = models.IntegerField(default=0)  # auto-disable after a streak
    notes = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Company sources"
        ordering = ["last_polled_at"]  # poll least-recently-seen first
        constraints = [
            models.UniqueConstraint(fields=["ats_type", "token"], name="jobs_cs_ats_token_uniq"),
        ]
        indexes = [models.Index(fields=["enabled", "last_polled_at"], name="jobs_cs_enabled_polled_idx")]

    def __str__(self):
        return f"{self.name} ({self.ats_type}:{self.token or self.board_url})"


class BlockRule(models.Model):
    RULE_TYPES = [("domain", "Domain"), ("company", "Company"), ("keyword", "Keyword"), ("regex", "Regex")]
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES, db_index=True)
    value = models.CharField(max_length=500)
    enabled = models.BooleanField(default=True)
    notes = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.rule_type}: {self.value}"

class UserSubmission(Job):
    class Meta: proxy = True; verbose_name = "User Submission"

class ActiveJob(Job):
    class Meta: proxy = True; verbose_name = "Active Job"
