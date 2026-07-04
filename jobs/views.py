import stripe
import json
import os
import secrets
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, Value, IntegerField, Count, Max
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.core.cache import cache
from django.utils.text import slugify
from django.http import HttpResponse, JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages 
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives

from .models import Job, Tool, Category, Subscriber, PendingSubscriber, BlogPost, SavedSearch, InterviewGuide, CertificationGuide
from .forms import JobPostForm, ContactForm
from .emails import send_job_alert, send_welcome_email, send_admin_new_subscriber_alert, send_confirmation_email
from .tool_catalog import all_canonical_names, resolve_tool_name

# Canonical tool display names (lowercased) for indexability checks.
_CANONICAL_TOOL_NAMES = {n.lower() for n in all_canonical_names()}

stripe.api_key = settings.STRIPE_SECRET_KEY


def _client_ip(request):
    # Rightmost X-Forwarded-For hop = the value our trusted proxy (Render's
    # load balancer) appended. The FIRST hop is client-supplied and spoofable —
    # keying rate limits on it let attackers rotate fake IPs per request.
    # (Same fix as tools/views.py.)
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[-1].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _rate_limited(request, action, limit=5, window_seconds=3600):
    """Returns True if this IP exceeded `limit` requests for `action` within the window.

    cache.add is atomic (returns False if the key already exists), so two
    concurrent first requests can't both reset the counter the way the old
    get_or_set + incr pattern could.
    """
    key = f"ratelimit:{action}:{_client_ip(request)}"
    if cache.add(key, 1, timeout=window_seconds):
        return False  # first request in this window
    try:
        count = cache.incr(key)
    except ValueError:
        # Key expired between add and incr — start a fresh window.
        cache.add(key, 1, timeout=window_seconds)
        return False
    return count > limit

TOOL_MAPPING = {
    'salesforce marketing cloud': 'Salesforce', 'sfmc': 'Salesforce', 'pardot': 'Salesforce',
    'marketo': 'Adobe', 'Adobe Experience Platform': 'Adobe', 'aep': 'Adobe',
    'hubspot': 'HubSpot', 'google analytics': 'Google', 'ga4': 'Google',
    'segment': 'Data Stack', 'tealium': 'Data Stack', 'snowflake': 'Data Stack',
    'outreach': 'Sales Tech', 'salesloft': 'Sales Tech', 'braze': 'Automation',
    'shopify': 'Commerce', 'the trade desk': 'AdTech'
}

# --- SEO CROSS-LINKING DATA ---
SEO_CROSS_CITIES = ["New York", "San Francisco", "Austin", "Chicago", "Seattle", "Boston", "Los Angeles", "Denver", "Atlanta", "London"]
SEO_CROSS_STATES = ["California", "Texas", "New York", "Florida", "Illinois", "Pennsylvania", "Washington", "Colorado"]

# Per-country city/region cross-links. On an international page the "by city" /
# "by state" rows must point to cities and regions IN THAT COUNTRY (not US),
# both for the visitor and for sane internal linking. Region label varies by
# country (state / province / emirate). Cities/regions with no jobs auto-noindex
# via the existing thin-content gate, so a quiet link is harmless.
COUNTRY_CROSS_CITIES = {
    "india": ["Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Pune", "Chennai", "Gurgaon", "Noida"],
    "united-kingdom": ["London", "Manchester", "Edinburgh", "Birmingham", "Bristol", "Leeds"],
    "singapore": ["Singapore"],
    "germany": ["Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne"],
    "france": ["Paris", "Lyon", "Toulouse"],
    "netherlands": ["Amsterdam", "Rotterdam", "Utrecht", "The Hague"],
    "canada": ["Toronto", "Vancouver", "Montreal", "Ottawa", "Calgary"],
    "australia": ["Sydney", "Melbourne", "Brisbane", "Perth"],
    "united-arab-emirates": ["Dubai", "Abu Dhabi"],
    "china": ["Shanghai", "Beijing", "Shenzhen", "Hong Kong"],
}
COUNTRY_CROSS_REGIONS = {
    "india": ["Karnataka", "Maharashtra", "Telangana", "Tamil Nadu", "Haryana"],
    "canada": ["Ontario", "British Columbia", "Quebec", "Alberta"],
    "australia": ["New South Wales", "Victoria", "Queensland"],
    "united-kingdom": ["England", "Scotland", "Wales"],
}
COUNTRY_REGION_LABEL = {
    "canada": "province", "united-arab-emirates": "emirate",
    "united-kingdom": "region", "germany": "region", "france": "region",
    "netherlands": "region",
}
# Reverse map: a city/region slug -> its country slug, so city pages (e.g.
# /bengaluru/jobs/) also show their own country's siblings instead of US ones.
_LOC_TO_COUNTRY = {}
for _c, _cities in COUNTRY_CROSS_CITIES.items():
    for _name in _cities:
        _LOC_TO_COUNTRY.setdefault(slugify(_name), _c)
for _c, _regions in COUNTRY_CROSS_REGIONS.items():
    for _name in _regions:
        _LOC_TO_COUNTRY.setdefault(slugify(_name), _c)


def _cross_links_for(loc_slug):
    """Return (cities, regions, region_label) for the country context of a page.
    Country pages and their member city/region pages get that country's links;
    everything else falls back to the US defaults."""
    country = None
    if loc_slug in COUNTRY_CROSS_CITIES:
        country = loc_slug
    elif loc_slug in _LOC_TO_COUNTRY:
        country = _LOC_TO_COUNTRY[loc_slug]
    if not country:
        return SEO_CROSS_CITIES, SEO_CROSS_STATES, "state"
    return (
        COUNTRY_CROSS_CITIES.get(country, []),
        COUNTRY_CROSS_REGIONS.get(country, []),
        COUNTRY_REGION_LABEL.get(country, "state"),
    )

# --- INDEXABLE LOCATIONS (anti-thin-content) ---
# The /<location>/jobs/ route is a catch-all, so Google found junk like
# /beverly-hills/jobs/ and /usa/jobs/. Only a CURATED set of locations gets an
# indexable page; everything else is served (for UX) but noindex'd.
_US_STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine",
    "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi",
    "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
    "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
    "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina",
    "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia",
    "Washington", "West Virginia", "Wisconsin", "Wyoming",
]
_SEO_COUNTRIES = [
    "united-states", "united-kingdom", "canada", "germany", "australia",
    "india", "ireland", "netherlands", "france", "spain", "singapore",
    "china", "united-arab-emirates",
]
# Country page slug -> (ISO-2 code, [location substrings]). Country pages match
# on the structured `country` field captured at ingest (reliable) OR any alias
# substring in the free-text location, so "/united-kingdom/" rolls up jobs
# stored as "London, UK", "London, England" or "London, GB" — not just the ones
# that literally contain "United Kingdom".
SEO_COUNTRY_MATCH = {
    "united-kingdom": ("GB", ["United Kingdom", ", UK", "England", "Scotland", "Wales", "London"]),
    "canada": ("CA", ["Canada"]),
    "germany": ("DE", ["Germany", "Deutschland", "Berlin", "Munich"]),
    "australia": ("AU", ["Australia"]),
    "india": ("IN", ["India", "Bengaluru", "Bangalore", "Mumbai", "Chennai", "Hyderabad", "Pune", "Delhi", "Gurgaon", "Gurugram", "Noida"]),
    "ireland": ("IE", ["Ireland", "Dublin"]),
    "netherlands": ("NL", ["Netherlands", "Amsterdam"]),
    "france": ("FR", ["France", "Paris"]),
    "spain": ("ES", ["Spain", "Madrid", "Barcelona"]),
    "singapore": ("SG", ["Singapore"]),
    "china": ("CN", ["China", "Shanghai", "Beijing", "Shenzhen", "Hong Kong"]),
    "united-arab-emirates": ("AE", ["United Arab Emirates", "UAE", "Dubai", "Abu Dhabi"]),
}
# Unique intro paragraph per country page. Gives each international landing page
# distinct, on-topic content so it isn't treated as thin/near-duplicate (the
# job lists alone can overlap). Keep these specific to the market's hubs and
# employers — no generic filler.
COUNTRY_INTROS = {
    "united-kingdom": "The UK is one of Europe's strongest MarTech hiring markets, with Marketing Operations, marketing automation and analytics roles concentrated in London, Manchester and Edinburgh. Expect demand for HubSpot, Salesforce, Marketo and Braze skills across fintech, SaaS and retail employers like Monzo, Wise and Deliveroo.",
    "india": "India's MarTech job market is growing fast across Bengaluru, Mumbai, Hyderabad, Pune and Gurgaon, driven by global SaaS companies and homegrown product firms. Marketing Operations, marketing automation and CDP roles are in demand, with strong hiring from vendors like Freshworks, CleverTap and MoEngage.",
    "singapore": "Singapore is the MarTech hub for APAC, with regional Marketing Operations and lifecycle roles based out of the city for companies scaling across Southeast Asia. Look for HubSpot, Salesforce Marketing Cloud, Braze and Segment skills at firms like Grab, Twilio and global vendor regional offices.",
    "germany": "Germany's MarTech scene centres on Berlin and Munich, spanning marketing automation, CRM operations and analytics roles. Employers like Delivery Hero, N26, Personio and Celonis hire for HubSpot, Salesforce, Marketo and customer data platform expertise.",
    "france": "France's MarTech market is anchored in Paris, with Marketing Operations and analytics roles at scaleups and enterprise SaaS firms. Contentsquare, Dataiku and Back Market are among employers hiring for marketing automation, CDP and digital analytics skills.",
    "netherlands": "The Netherlands — especially Amsterdam — is a key European MarTech hub, with Marketing Operations and lifecycle roles at fintech and SaaS companies like Adyen, Mollie and Bird. HubSpot, Salesforce, Braze and Segment skills are consistently in demand.",
    "canada": "Canada's MarTech hiring spans Toronto, Vancouver and Montréal, covering Marketing Operations, marketing automation and analytics. Employers like Shopify, Lightspeed, Wealthsimple and 1Password hire for HubSpot, Marketo, Salesforce and CDP expertise.",
    "united-arab-emirates": "The UAE — Dubai and Abu Dhabi — is the fastest-growing MarTech market in the Middle East, with Marketing Operations and lifecycle roles at regional tech and commerce firms like Careem and Kitopi. Demand centres on Salesforce, HubSpot and marketing automation skills.",
    "china": "China's MarTech roles, concentrated in Shanghai, Beijing and Shenzhen, sit largely within global companies' regional teams and international-facing product groups. Marketing Operations, analytics and marketing automation skills are most relevant for English-language postings.",
    "australia": "Australia's MarTech market spans Sydney and Melbourne, with Marketing Operations, marketing automation and analytics roles at firms like Canva, Airwallex and SafetyCulture. HubSpot, Salesforce, Braze and Segment expertise is widely sought.",
}
# Full state name -> USPS code, so a state page (e.g. /california/jobs/) rolls
# up city jobs stored with the abbreviation ("San Francisco, CA, United States").
US_STATE_ABBR = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}
_SEO_CITIES = [
    "New York", "San Francisco", "Austin", "Chicago", "Seattle", "Boston",
    "Los Angeles", "Denver", "Atlanta", "Dallas", "Miami", "Toronto", "London",
]
INDEXABLE_LOCATION_SLUGS = (
    {"remote"} | set(_SEO_COUNTRIES)
    | {slugify(s) for s in _US_STATES} | {slugify(c) for c in _SEO_CITIES}
    # International city/region pages linked from country pages must be indexable
    # too (they still auto-noindex while empty via the thin-content gate).
    | {slugify(c) for cities in COUNTRY_CROSS_CITIES.values() for c in cities}
    | {slugify(r) for regions in COUNTRY_CROSS_REGIONS.values() for r in regions}
)
# Old/abbreviated slugs -> canonical slug (301 redirected to avoid duplicates).
LOCATION_ALIASES = {
    "usa": "united-states", "us": "united-states", "u-s-a": "united-states",
    "uk": "united-kingdom", "u-k": "united-kingdom", "nyc": "new-york",
    "sf": "san-francisco", "la": "los-angeles", "dfw": "dallas",
    "uae": "united-arab-emirates", "u-a-e": "united-arab-emirates",
}

# --- JOB-TITLE PAGES (programmatic SEO for high-intent title queries) ---
# Curated only: keeps these pages high-quality and prevents arbitrary slugs
# from generating thin pages. Each has unique intro copy for SEO.
TITLE_JOBS = {
    "marketing-operations-manager": {
        "name": "Marketing Operations Manager",
        "kw": ["marketing operations manager", "marketing ops manager", "mops manager", "manager, marketing operations"],
        "intro": "Marketing Operations Managers own the marketing tech stack, campaign operations, lead lifecycle, and reporting — the connective tissue between marketing, sales, and data.",
        "skills": "Marketo, HubSpot, Salesforce, lead routing, attribution, reporting",
    },
    "marketing-operations-specialist": {
        "name": "Marketing Operations Specialist",
        "kw": ["marketing operations specialist", "marketing ops specialist", "mops specialist", "marketing operations analyst"],
        "intro": "Marketing Operations Specialists run day-to-day campaign execution, list management, automation builds, and QA inside the marketing automation platform.",
        "skills": "HubSpot, Marketo, email QA, segmentation, workflows",
    },
    # RevOps intentionally removed: the screener EXCLUDES Revenue Operations
    # roles, so this programmatic page was always empty and contradicted our
    # positioning. The old /revenue-operations-manager-jobs/ URL 301-redirects
    # to marketing-operations-manager (see jobs/urls.py).
    "marketing-automation-specialist": {
        "name": "Marketing Automation Specialist",
        "kw": ["marketing automation specialist", "marketing automation manager", "automation specialist"],
        "intro": "Marketing Automation Specialists build and optimize nurture programs, triggered journeys, scoring, and integrations across the automation platform.",
        "skills": "Marketo, Pardot, HubSpot, lead scoring, nurture programs",
    },
    "salesforce-administrator": {
        "name": "Salesforce Administrator",
        "kw": ["salesforce administrator", "salesforce admin", "sfdc administrator"],
        "intro": "Salesforce Administrators configure and maintain the CRM — objects, automation, permissions, reports, and integrations that keep revenue teams running.",
        "skills": "Salesforce, flows, reports, data hygiene, integrations",
    },
    "salesforce-marketing-cloud-developer": {
        "name": "Salesforce Marketing Cloud Developer",
        "kw": ["marketing cloud developer", "sfmc developer", "salesforce marketing cloud"],
        "intro": "Salesforce Marketing Cloud Developers build journeys, AMPscript/SSJS, data extensions, and integrations on SFMC for enterprise lifecycle marketing.",
        "skills": "SFMC, AMPscript, SSJS, Journey Builder, SQL",
    },
    "hubspot-administrator": {
        "name": "HubSpot Administrator",
        "kw": ["hubspot administrator", "hubspot admin", "hubspot specialist", "hubspot manager"],
        "intro": "HubSpot Administrators own the HubSpot portal — workflows, properties, reporting, and the CRM/marketing integrations that power inbound and lifecycle.",
        "skills": "HubSpot, workflows, CRM, reporting, integrations",
    },
    "marketo-specialist": {
        "name": "Marketo Specialist",
        "kw": ["marketo specialist", "marketo admin", "marketo developer", "marketo consultant"],
        "intro": "Marketo Specialists build smart campaigns, programs, scoring, and integrations in Adobe Marketo Engage for demand generation and lifecycle teams.",
        "skills": "Marketo, smart campaigns, scoring, tokens, integrations",
    },
    "lifecycle-marketing-manager": {
        "name": "Lifecycle Marketing Manager",
        "kw": ["lifecycle marketing manager", "lifecycle marketing", "crm marketing manager", "retention marketing manager"],
        "intro": "Lifecycle Marketing Managers own retention and engagement across email, push, and in-app — building journeys that move customers from onboarding to loyalty.",
        "skills": "Braze, Iterable, Klaviyo, segmentation, retention",
    },
    "crm-manager": {
        "name": "CRM Manager",
        "kw": ["crm manager", "crm marketing manager", "customer relationship management manager"],
        "intro": "CRM Managers own the customer database and direct-marketing programs — segmentation, campaigns, and the platforms that drive repeat engagement.",
        "skills": "CRM, segmentation, email, campaign management",
    },
    "marketing-analytics-manager": {
        "name": "Marketing Analytics Manager",
        "kw": ["marketing analytics manager", "marketing analytics", "marketing data analyst", "analytics manager marketing"],
        "intro": "Marketing Analytics Managers turn campaign and product data into insight — owning attribution, dashboards, experimentation, and the measurement stack.",
        "skills": "GA4, SQL, attribution, dashboards, experimentation",
    },
    "demand-generation-manager": {
        "name": "Demand Generation Manager",
        "kw": ["demand generation manager", "demand gen manager", "demand generation"],
        "intro": "Demand Generation Managers drive pipeline — owning multi-channel campaigns, lead funnels, and the operations and analytics that scale them.",
        "skills": "Marketo, HubSpot, paid, ABM, pipeline analytics",
    },
    "email-marketing-manager": {
        "name": "Email Marketing Manager",
        "kw": ["email marketing manager", "email marketing specialist", "email marketing"],
        "intro": "Email Marketing Managers own the email channel end to end — strategy, segmentation, automation, deliverability, and performance.",
        "skills": "Klaviyo, Iterable, HubSpot, deliverability, segmentation",
    },
    "marketing-technologist": {
        "name": "Marketing Technologist",
        "kw": ["marketing technologist", "martech engineer", "marketing technology manager", "martech manager"],
        "intro": "Marketing Technologists architect and integrate the marketing stack — connecting platforms, data, and tooling so campaigns run reliably at scale.",
        "skills": "CDP, integrations, APIs, tag management, data",
    },
    "growth-marketing-manager": {
        "name": "Growth Marketing Manager",
        "kw": ["growth marketing manager", "growth marketer", "growth manager marketing"],
        "intro": "Growth Marketing Managers run experiments across acquisition, activation, and retention — pairing creative testing with analytics and automation.",
        "skills": "experimentation, analytics, lifecycle, paid, automation",
    },
    "campaign-operations-manager": {
        "name": "Campaign Operations Manager",
        "kw": ["campaign operations manager", "campaign manager", "campaign operations"],
        "intro": "Campaign Operations Managers run the campaign engine — builds, QA, scheduling, and the cross-team process that gets marketing live on time.",
        "skills": "Marketo, HubSpot, QA, project management, workflows",
    },
}

def job_list(request):
    query = request.GET.get("q", "").strip()
    vendor_query = request.GET.get("vendor", "").strip()
    location_query = request.GET.get("l", "").strip()
    country_query = request.GET.get("country", "").strip()
    work_arrangement_filter = request.GET.get("arrangement", "").strip().lower()
    role_type_filter = request.GET.get("rtype", "").strip().lower()
    tool_filter = request.GET.get("tool", "").strip()
    sort = request.GET.get("sort", "").strip().lower()

    jobs = Job.objects.filter(is_active=True, screening_status="approved").prefetch_related("tools")

    if tool_filter:
        jobs = jobs.filter(tools__slug=tool_filter)

    if vendor_query:
        if vendor_query == "General":
            jobs = jobs.filter(tools__isnull=True)
        else:
            matching_tool_ids = []
            for tool in Tool.objects.all():
                if TOOL_MAPPING.get(tool.name.lower(), tool.name) == vendor_query:
                    matching_tool_ids.append(tool.id)
            jobs = jobs.filter(tools__id__in=matching_tool_ids)
    
    elif query:
        search_q = Q(title__icontains=query) | Q(company__icontains=query) | Q(tools__name__icontains=query)
        jobs = jobs.filter(search_q).annotate(
            relevance=Case(
                When(title__icontains=query, then=Value(10)),
                When(Q(company__icontains=query) | Q(tools__name__icontains=query), then=Value(5)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
    
    if sort == "oldest":
        jobs = jobs.order_by('created_at')
    elif query:
        jobs = jobs.order_by('-is_pinned', '-relevance', '-created_at')
    else:
        jobs = jobs.order_by('-is_pinned', '-created_at')

    if location_query:
        jobs = jobs.filter(location__icontains=location_query)
    
    if country_query:
        jobs = jobs.filter(location__icontains=country_query)

    if work_arrangement_filter:
        jobs = jobs.filter(work_arrangement__iexact=work_arrangement_filter)
    
    if role_type_filter:
        jobs = jobs.filter(role_type__iexact=role_type_filter)

    # On the unfiltered homepage, show only the latest 10 roles with a
    # "View all jobs" link. Active searches/filters (or ?all=1) get the full
    # paginated list.
    has_filters = bool(
        query or vendor_query or location_query or country_query
        or work_arrangement_filter or role_type_filter or tool_filter or sort
    )
    show_all = request.GET.get("all") == "1"
    limited = not has_filters and not show_all

    distinct_jobs = jobs.distinct()
    total_count = distinct_jobs.count()

    if limited:
        paginator = Paginator(distinct_jobs, 10)
        jobs_page = paginator.get_page(1)
    else:
        paginator = Paginator(distinct_jobs, 25)
        page_number = request.GET.get("page")
        jobs_page = paginator.get_page(page_number)

    # Querystring with all current filters except page, so pagination links keep them.
    params = request.GET.copy()
    params.pop("page", None)
    filter_qs = params.urlencode()

    featured_stacks = _build_featured_stacks()

    # Real salary preview for the homepage teaser. Reuse the cached salary-guide
    # aggregates if present; never trigger the expensive computation here.
    salary_cache = cache.get('salary_guide_data_v2') or []
    salary_preview = []
    if salary_cache:
        top = salary_cache[:5]
        max_val = max((s['avg_max'] for s in top), default=1) or 1
        for s in top:
            salary_preview.append({
                'name': s['tool'].name,
                'slug': s['tool'].slug,
                'range': f"${s['avg_min']//1000}K–${s['avg_max']//1000}K",
                'pct': max(35, int(s['avg_max'] / max_val * 100)),
            })

    return render(request, "jobs/job_list.html", {
        "salary_preview": salary_preview,
        "jobs": jobs_page,
        "query": query,
        "location_filter": location_query,
        "selected_country": country_query,
        "vendor_filter": vendor_query,
        "current_arrangement": work_arrangement_filter,
        "current_rtype": role_type_filter,
        "selected_tool": tool_filter,
        "current_sort": sort,
        "filter_qs": filter_qs,
        "limited": limited,
        "total_count": total_count,
        "featured_stacks": featured_stacks,
    })

# Curated "Browse by stack" cards: preferred slug -> short role line.
STACK_META = {
    "salesforce": "Marketing Cloud, CRM, Admin",
    "hubspot": "Marketing Hub, Ops, automation",
    "marketo": "Campaigns, lead scoring, MOps",
    "braze": "Lifecycle, push, in-app",
    "adobe": "Experience Platform, AEP, AEM",
    "klaviyo": "Email & SMS, DTC retention",
    "segment": "CDP, tracking, identity",
    "snowflake": "Warehouse, modeling, BI",
}
_STACK_TINTS = ["tint-navy", "tint-amber", "tint-violet", "tint-ink", "tint-green"]

def _build_featured_stacks(limit=8):
    """Data-driven homepage stack cards: real slugs + live job counts."""
    approved = Q(jobs__is_active=True, jobs__screening_status="approved")
    found = {
        t.slug: t for t in Tool.objects.filter(slug__in=list(STACK_META.keys()))
        .annotate(job_count=Count("jobs", filter=approved))
    }
    cards = []
    for slug, role in STACK_META.items():
        tool = found.get(slug)
        if not tool or not tool.job_count:
            continue
        cards.append({"slug": tool.slug, "name": tool.name, "role": role, "count": tool.job_count})

    # Fill any remaining slots with the next most popular tools.
    if len(cards) < limit:
        used = {c["slug"] for c in cards}
        extra = (
            Tool.objects.annotate(job_count=Count("jobs", filter=approved))
            .filter(job_count__gt=0).exclude(slug__in=used).order_by("-job_count")[: limit - len(cards)]
        )
        for tool in extra:
            cards.append({"slug": tool.slug, "name": tool.name, "role": "MarTech roles", "count": tool.job_count})

    cards = cards[:limit]
    for i, card in enumerate(cards):
        card["tint"] = _STACK_TINTS[i % len(_STACK_TINTS)]
        card["initial"] = card["name"][:1]
    return cards

# --- CATEGORY LANDING PAGES (Engineering / Operations / Data) ---
CATEGORY_CONFIG = {
    "engineering": {
        "name": "Engineering",
        "eyebrow": "Build the systems",
        "description": "MarTech engineering, CDP, integrations, and analytics/tag-management implementation — the people who build and own the systems behind the stack.",
        "placeholder": "Search engineering jobs…",
        "keywords": ["engineer", "developer", "architect", "technologist", "integration",
                     "engineering", "implementation", "tag management", "tagging",
                     "analytics engineer", "platform"],
        "tool_slugs": ["segment", "dbt", "snowflake", "ga4", "mparticle", "customer-io",
                       "rudderstack", "amplitude", "bigquery"],
    },
    "operations": {
        "name": "Operations",
        "eyebrow": "Run the stack",
        "description": "Marketing Operations, marketing automation, and campaign operations — the people who run the platforms and orchestrate campaigns.",
        "placeholder": "Search operations jobs…",
        "keywords": ["marketing operations", "marketing ops", "mops",
                     "marketing automation", "campaign operations", "administrator"],
        "tool_slugs": ["hubspot", "marketo", "salesforce", "pardot",
                       "marketing-cloud", "eloqua"],
    },
    "data": {
        "name": "Data",
        "eyebrow": "Turn data into growth",
        "description": "Analytics engineering, BI, and data roles — the people who turn marketing data into insight and measurable growth.",
        "placeholder": "Search data jobs…",
        "keywords": ["data", "analytics", "analyst", "insight", "reporting", "intelligence",
                     "measurement", "attribution", "business intelligence"],
        "tool_slugs": ["snowflake", "segment", "ga4", "amplitude", "looker", "bigquery",
                       "tableau", "mixpanel", "dbt"],
    },
}

def category_detail(request, slug):
    config = CATEGORY_CONFIG.get(slug)
    if not config:
        raise Http404("Unknown category")

    query = request.GET.get("q", "").strip()
    location_query = request.GET.get("l", "").strip()
    tool_filter = request.GET.get("tool", "").strip()
    work_arrangement_filter = request.GET.get("arrangement", "").strip().lower()

    jobs = Job.objects.filter(is_active=True, screening_status="approved").prefetch_related("tools")

    # Prefer stored function field; fall back to keyword+tool matching for
    # legacy jobs that haven't been classified yet (function='other').
    classified = jobs.filter(function=slug)
    unclassified = jobs.filter(function="other")
    cat_q = Q()
    for kw in config["keywords"]:
        cat_q |= Q(title__icontains=kw)
    cat_q |= Q(tools__slug__in=config["tool_slugs"])
    unclassified = unclassified.filter(cat_q)
    jobs = (classified | unclassified)

    # Optional user refinements within the category.
    if query:
        jobs = jobs.filter(
            Q(title__icontains=query) | Q(company__icontains=query) | Q(tools__name__icontains=query)
        )
    if tool_filter:
        jobs = jobs.filter(tools__slug=tool_filter)
    if location_query:
        jobs = jobs.filter(location__icontains=location_query)
    if work_arrangement_filter:
        jobs = jobs.filter(work_arrangement__iexact=work_arrangement_filter)

    jobs = jobs.order_by("-is_pinned", "-created_at").distinct()
    total_count = jobs.count()

    paginator = Paginator(jobs, 25)
    jobs_page = paginator.get_page(request.GET.get("page"))

    # Top tech stacks within this category (only those that have live jobs).
    top_stacks = (
        Tool.objects.filter(slug__in=config["tool_slugs"])
        .annotate(job_count=Count("jobs", filter=Q(jobs__is_active=True, jobs__screening_status="approved")))
        .filter(job_count__gt=0)
        .order_by("-job_count")[:6]
    )

    # Tool options for the in-page filter dropdown.
    category_tools = Tool.objects.filter(slug__in=config["tool_slugs"]).order_by("name")

    params = request.GET.copy()
    params.pop("page", None)
    filter_qs = params.urlencode()

    return render(request, "jobs/category.html", {
        "category": config,
        "category_slug": slug,
        "jobs": jobs_page,
        "total_count": total_count,
        "page_noindex": total_count == 0,
        "query": query,
        "location_filter": location_query,
        "selected_tool": tool_filter,
        "current_arrangement": work_arrangement_filter,
        "top_stacks": top_stacks,
        "category_tools": category_tools,
        "filter_qs": filter_qs,
    })

def all_jobs(request):
    """Dedicated browse-all-jobs board (the 'Jobs' nav destination)."""
    query = request.GET.get("q", "").strip()
    location_query = request.GET.get("l", "").strip()
    tool_filter = request.GET.get("tool", "").strip()
    work_arrangement_filter = request.GET.get("arrangement", "").strip().lower()
    function = request.GET.get("function", "").strip().lower()
    sort = request.GET.get("sort", "").strip().lower()

    jobs = Job.objects.filter(is_active=True, screening_status="approved").prefetch_related("tools")

    # Optional function scope (Engineering / Operations / Data).
    # Prefer stored function field; fall back to keyword matching for unclassified jobs.
    if function in CATEGORY_CONFIG:
        config = CATEGORY_CONFIG[function]
        cat_q = Q()
        for kw in config["keywords"]:
            cat_q |= Q(title__icontains=kw)
        cat_q |= Q(tools__slug__in=config["tool_slugs"])
        jobs = jobs.filter(Q(function=function) | (Q(function="other") & cat_q))

    if query:
        jobs = jobs.filter(
            Q(title__icontains=query) | Q(company__icontains=query) | Q(tools__name__icontains=query)
        )
    if tool_filter:
        jobs = jobs.filter(tools__slug=tool_filter)
    if location_query:
        jobs = jobs.filter(location__icontains=location_query)
    if work_arrangement_filter:
        jobs = jobs.filter(work_arrangement__iexact=work_arrangement_filter)

    if sort == "oldest":
        jobs = jobs.order_by("created_at")
    else:
        jobs = jobs.order_by("-is_pinned", "-created_at")

    jobs = jobs.distinct()
    total_count = jobs.count()

    paginator = Paginator(jobs, 25)
    jobs_page = paginator.get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)
    filter_qs = params.urlencode()

    return render(request, "jobs/all_jobs.html", {
        "jobs": jobs_page,
        "total_count": total_count,
        "query": query,
        "location_filter": location_query,
        "selected_tool": tool_filter,
        "current_arrangement": work_arrangement_filter,
        "current_function": function,
        "current_sort": sort,
        "view_mode": request.GET.get("view", "list"),
        "filter_qs": filter_qs,
        "popular_titles": [{"slug": s, "name": c["name"]} for s, c in TITLE_JOBS.items()],
    })

def title_jobs(request, title_slug):
    """Programmatic job-title landing page (e.g. /marketing-operations-manager-jobs/)."""
    cfg = TITLE_JOBS.get(title_slug)
    if not cfg:
        raise Http404("Unknown role")

    q = Q()
    for kw in cfg["kw"]:
        q |= Q(title__icontains=kw)
    jobs = (
        Job.objects.filter(is_active=True, screening_status="approved")
        .filter(q).prefetch_related("tools").distinct()
        .order_by("-is_pinned", "-created_at")
    )
    total_count = jobs.count()
    paginator = Paginator(jobs, 20)
    jobs_page = paginator.get_page(request.GET.get("page"))

    related = [{"slug": s, "name": c["name"]} for s, c in TITLE_JOBS.items() if s != title_slug][:9]

    return render(request, "jobs/title_jobs.html", {
        "jobs": jobs_page,
        "total_count": total_count,
        "title_name": cfg["name"],
        "title_slug": title_slug,
        "intro": cfg["intro"],
        "skills": cfg.get("skills", ""),
        "related_titles": related,
        "page_noindex": total_count == 0,
    })


# Clean-URL blog sections. The ?category= filter works but is deliberately
# noindexed (FILTER_PARAMS), so each section gets an indexable path with its
# own title/meta/intro — /blog/ai-in-martech/ is the flagship.
BLOG_SECTIONS = {
    'ai-in-martech': {
        'category': 'AI in MarTech',
        'title': 'AI in MarTech — Practical Guides for Marketing Ops Professionals',
        'meta': 'How AI is changing Marketing Operations, Marketing Automation, and MarTech careers: honest, practitioner-grade guides on AI skills, tools, and staying ahead.',
        'intro': 'No hype, no doom — practitioner-grade coverage of how AI is actually changing Marketing Operations work, which skills matter, and how to stay ahead of it.',
    },
    'salary-guides': {
        'category': 'Salary Guides',
        'title': 'MarTech & Marketing Ops Salary Guides',
        'meta': 'Salary guides for Marketing Operations, Marketing Automation, Salesforce, HubSpot, Marketo, and MarTech roles — by experience level, city, and market.',
        'intro': 'Compensation guides for MarTech and Marketing Operations roles, by platform, seniority, and market.',
    },
    'career-advice': {
        'category': 'Career Advice',
        'title': 'MarTech Career Advice & Role Guides',
        'meta': 'Role guides and career advice for Marketing Operations, MarTech engineering, and marketing analytics professionals.',
        'intro': 'Role guides, career paths, and hiring insight for MarTech and Marketing Ops professionals.',
    },
    'tech-stacks': {
        'category': 'Tech Stacks',
        'title': 'MarTech Stacks & Platform Guides',
        'meta': 'Deep dives on MarTech platforms and stacks: Salesforce, HubSpot, Marketo, Braze, Segment, Adobe Experience Cloud, and more.',
        'intro': 'Platform deep-dives and stack guides for the tools MarTech teams run on.',
    },
}


def blog_category(request, section_slug):
    """Indexable landing page for one blog category (e.g. /blog/ai-in-martech/)."""
    section = BLOG_SECTIONS.get(section_slug)
    if not section:
        raise Http404
    posts = BlogPost.objects.filter(
        is_published=True, category__iexact=section['category']
    ).order_by('-published_at')
    return render(request, 'jobs/blog_list.html', {
        'posts': posts,
        'interview_guides': [],
        'cert_guides': [],
        'search_query': '',
        'current_category': section['category'],
        'is_hub': False,
        'section_title': section['title'],
        'section_meta': section['meta'],
        'section_intro': section['intro'],
        'canonical_url': f'https://martechjobs.io/blog/{section_slug}/',
        # A section with no posts yet must not be indexed (thin content) —
        # keeps the robots meta consistent with BlogSectionSitemap's gating.
        'page_noindex': not posts.exists(),
    })


def blog_list(request):
    search_query = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '').strip()

    all_posts = BlogPost.objects.filter(is_published=True).order_by('-published_at')

    if search_query:
        all_posts = all_posts.filter(
            Q(title__icontains=search_query) |
            Q(content__icontains=search_query) |
            Q(excerpt__icontains=search_query)
        )

    if category_filter:
        all_posts = all_posts.filter(category__iexact=category_filter)

    interview_guides = (
        InterviewGuide.objects.filter(is_published=True)
        .select_related('tool').order_by('-updated_at')
    )
    cert_guides = (
        CertificationGuide.objects.filter(is_published=True)
        .select_related('tool').order_by('-updated_at')
    )

    # Hub mode: organize posts into sections when no filter is active.
    is_hub = not search_query and not category_filter
    ctx = {
        'posts': all_posts,
        'interview_guides': interview_guides,
        'cert_guides': cert_guides,
        'search_query': search_query,
        'current_category': category_filter,
        'is_hub': is_hub,
    }

    if is_hub:
        base = BlogPost.objects.filter(is_published=True).order_by('-published_at')
        ctx['featured_post'] = base.first()
        ctx['latest_posts'] = list(base[1:4])
        ctx['tech_posts'] = list(base.filter(category='Tech Stacks')[:4])
        ctx['career_posts'] = list(base.filter(category='Career Advice')[:4])
        ctx['salary_posts'] = list(base.filter(category='Salary Guides')[:3])
        ctx['news_posts'] = list(base.filter(category='Industry News')[:3])

    return render(request, 'jobs/blog_list.html', ctx)

def _extract_post_faqs(html):
    """Pull Q/A pairs out of a post's 'Frequently Asked Questions' section
    (the AEO prompt makes every generated post end with <h2>FAQ…</h2> followed
    by <h3> question / <p> answer pairs). Returns [(question, answer)] so the
    template can emit FAQPage JSON-LD — the content is already answer-shaped;
    this just marks it up. Empty list when a post has no FAQ block."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html or "", "html.parser")
        faq_h2 = None
        for h2 in soup.find_all("h2"):
            if "frequently asked" in h2.get_text(" ", strip=True).lower():
                faq_h2 = h2
                break
        if not faq_h2:
            return []
        faqs = []
        node = faq_h2.find_next_sibling()
        question, answer_parts = None, []
        while node is not None and node.name != "h2":
            if node.name == "h3":
                if question and answer_parts:
                    faqs.append((question, " ".join(answer_parts)))
                question, answer_parts = node.get_text(" ", strip=True), []
            elif question and node.name in ("p", "ul", "ol"):
                text = node.get_text(" ", strip=True)
                if text:
                    answer_parts.append(text)
            node = node.find_next_sibling()
        if question and answer_parts:
            faqs.append((question, " ".join(answer_parts)))
        return faqs[:8]
    except Exception:
        return []


def post_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug, is_published=True)
    related_posts = BlogPost.objects.filter(is_published=True).exclude(id=post.id).order_by('-published_at')[:2]
    sidebar_jobs = Job.objects.filter(is_active=True, screening_status='approved').order_by('-is_featured', '-created_at')[:2]

    # FAQPage schema from the post's own FAQ section (cached — parsing is
    # pure-function of the content, keyed on updated_at).
    cache_key = f"post_faqs:{post.id}:{post.updated_at.timestamp() if post.updated_at else 0}"
    faq_items = cache.get(cache_key)
    if faq_items is None:
        faq_items = _extract_post_faqs(post.content)
        cache.set(cache_key, faq_items, 60 * 60 * 24)

    return render(request, 'jobs/post_detail.html', {
        'post': post,
        'related_posts': related_posts,
        'sidebar_jobs': sidebar_jobs,
        'faq_items': faq_items,
    })

# --- SEO: LANDING PAGE GENERATOR ---
def seo_landing_page(request, location_slug=None, tool_slug=None):
    # 301 abbreviated/old location slugs to the canonical one (no duplicates).
    if location_slug and location_slug.lower() in LOCATION_ALIASES:
        canonical = LOCATION_ALIASES[location_slug.lower()]
        if tool_slug:
            return redirect('seo_tool_loc', location_slug=canonical, tool_slug=tool_slug, permanent=True)
        return redirect('seo_loc_only', location_slug=canonical, permanent=True)

    tool = None
    if tool_slug:
        clean_tool_slug = tool_slug.replace("-jobs", "")
        tool = get_object_or_404(Tool, slug=clean_tool_slug)

    SEO_LOCATIONS = {
        "united-states": "United States",
    }

    location_name = "Remote"
    if location_slug:
        location_name = SEO_LOCATIONS.get(location_slug.lower(), location_slug.replace("-", " ").title())

    jobs = Job.objects.filter(is_active=True, screening_status='approved')
    if tool: jobs = jobs.filter(tools=tool)
    _loc_slug = (location_slug or "").lower()
    if location_name == "Remote":
        jobs = jobs.filter(work_arrangement="remote")
    elif _loc_slug in SEO_COUNTRY_MATCH:
        # Country page: match the structured `country` ISO field (captured at
        # ingest) OR any alias substring in the free-text location, so jobs
        # stored as "London, UK" / "London, England" / "London, GB" all roll up.
        iso, aliases = SEO_COUNTRY_MATCH[_loc_slug]
        country_q = Q(country=iso)
        for alias in aliases:
            country_q |= Q(location__icontains=alias)
        jobs = jobs.filter(country_q)
    elif location_name != "United States":
        state_abbr = US_STATE_ABBR.get(location_name.lower())
        if state_abbr:
            # State page: match the full name OR the USPS code as it appears in
            # stored locations ("San Francisco, CA, United States").
            jobs = jobs.filter(
                Q(location__icontains=location_name)
                | Q(location__icontains=f", {state_abbr},")
                | Q(location__iendswith=f", {state_abbr}")
            )
        else:
            jobs = jobs.filter(location__icontains=location_name)

    jobs = jobs.order_by('-is_pinned', '-created_at')
    total_count = jobs.count()

    from datetime import date as _date
    _year = _date.today().year

    if tool and location_name:
        page_title = f"{location_name} {tool.name} Jobs"
        meta_desc = f"Apply to the best {tool.name} jobs in {location_name}. Curated Marketing Operations roles."
        header_text = f"{location_name} <span class='text-martech-green'>{tool.name}</span> Jobs"
    elif tool:
        page_title = f"{tool.name} Jobs"
        meta_desc = f"Find top {tool.name} roles. Marketing Automation & Ops jobs."
        header_text = f"Top <span class='text-martech-green'>{tool.name}</span> Jobs"
    else:
        page_title = f"{total_count} {location_name} MarTech Jobs {_year}"
        meta_desc = f"Browse {total_count} MarTech and Marketing Operations jobs in {location_name}. Updated daily."
        header_text = f"MarTech Jobs in <span class='text-martech-green'>{location_name}</span>"
    paginator = Paginator(jobs, 20)
    jobs_page = paginator.get_page(request.GET.get('page'))

    # Index only curated, populated pages. Non-curated locations (Beverly Hills,
    # Noida, …) and non-canonical tools are noindex'd to avoid thin auto-pages.
    loc_indexable = (not location_slug) or (location_slug.lower() in INDEXABLE_LOCATION_SLUGS)
    tool_indexable = (tool is None) or (tool.name.lower() in _CANONICAL_TOOL_NAMES)
    page_noindex = (total_count == 0) or (not loc_indexable) or (not tool_indexable)

    # Unique intro + remote cross-link for international country pages (only on
    # the location-only page, not tool combos, to keep tool pages focused).
    country_intro = None
    is_country_page = False
    if not tool and _loc_slug in SEO_COUNTRY_MATCH:
        is_country_page = True
        country_intro = COUNTRY_INTROS.get(_loc_slug)

    # Country-aware cross-links: on India/UK/etc. (and their member cities), the
    # "by city / by region" rows point to that country, not the US.
    cross_cities, cross_states, region_label = _cross_links_for(_loc_slug)

    return render(request, 'jobs/seo_landing.html', {
        'tool': tool, 'jobs': jobs_page, 'total_count': total_count,
        'page_noindex': page_noindex,
        'custom_title': page_title, 'custom_header': header_text, 'custom_desc': meta_desc,
        'is_seo_landing': True, 'location_name': location_name,
        'country_intro': country_intro, 'is_country_page': is_country_page,
        'cross_cities': cross_cities, 'cross_states': cross_states,
        'region_label': region_label,
    })

def market_stats(request):
    """MarTech Job Market Statistics — a citable, auto-refreshing stats page
    computed from LIVE listings (AEO: answer engines cite pages that are the
    source of a number, and every figure here is real per the site's content
    rules). Cached 1h; the underlying data changes at most daily via the cron.
    """
    data = cache.get('market_stats_v1')
    if not data:
        live = Job.objects.filter(is_active=True, screening_status='approved')
        total = live.count()
        remote = live.filter(work_arrangement='remote').count()
        hybrid = live.filter(work_arrangement='hybrid').count()

        # Jobs by platform/tool (canonical tools only, with live jobs).
        canonical = {n.lower() for n in all_canonical_names()}
        tools = (
            Tool.objects.annotate(
                n=Count('jobs', filter=Q(jobs__is_active=True, jobs__screening_status='approved'))
            ).filter(n__gt=0).order_by('-n')
        )
        by_tool = [(t.name, t.n) for t in tools if (t.name or '').lower() in canonical][:15]

        # Jobs by function.
        func_labels = {'operations': 'Marketing Operations', 'engineering': 'MarTech Engineering',
                       'data': 'Marketing Analytics & Data', 'other': 'Other'}
        by_function = [
            (func_labels.get(r['function'], r['function']), r['n'])
            for r in live.values('function').annotate(n=Count('id')).order_by('-n')
        ]

        # Jobs by country (structured field first, text fallback via the same
        # helper the JobPosting schema uses).
        country_names = {
            'US': 'United States', 'GB': 'United Kingdom', 'IN': 'India', 'CA': 'Canada',
            'DE': 'Germany', 'FR': 'France', 'NL': 'Netherlands', 'SG': 'Singapore',
            'AE': 'United Arab Emirates', 'AU': 'Australia', 'IE': 'Ireland', 'ES': 'Spain',
            'CN': 'China', 'HK': 'Hong Kong', 'PL': 'Poland', 'PT': 'Portugal',
            'IT': 'Italy', 'SE': 'Sweden', 'MX': 'Mexico', 'BR': 'Brazil',
        }
        country_counts = {}
        for job in live.only('country', 'location'):
            code = job.get_schema_country()
            country_counts[code] = country_counts.get(code, 0) + 1
        by_country = sorted(
            ((country_names.get(c, c), n) for c, n in country_counts.items()),
            key=lambda x: -x[1],
        )[:10]

        # Salary transparency: how many listings publish a range, and the
        # midpoint spread across those that do (USD-denominated ones dominate).
        sal_mins, sal_maxes = [], []
        for job in live.exclude(salary_range__isnull=True).exclude(salary_range=''):
            mn, mx = (job.get_salary_min_max() or (None, None))
            if mn and mx and mn > 10000:  # ignore hourly/garbage parses
                sal_mins.append(mn); sal_maxes.append(mx)
        with_salary = len(sal_mins)
        median_min = sorted(sal_mins)[with_salary // 2] if with_salary else None
        median_max = sorted(sal_maxes)[with_salary // 2] if with_salary else None

        data = {
            'total': total,
            'remote': remote,
            'remote_pct': round(remote * 100 / total) if total else 0,
            'hybrid': hybrid,
            'companies': live.values('company').distinct().count(),
            'by_tool': by_tool,
            'by_function': by_function,
            'by_country': by_country,
            'with_salary': with_salary,
            'salary_pct': round(with_salary * 100 / total) if total else 0,
            'median_min': median_min,
            'median_max': median_max,
            'updated': timezone.now(),
        }
        cache.set('market_stats_v1', data, 3600)

    return render(request, 'jobs/market_stats.html', {
        **data,
        'canonical_url': 'https://martechjobs.io/martech-job-market-statistics/',
    })


def salary_guide(request):
    data = cache.get('salary_guide_data_v2')
    if not data:
        # Eligible tools (those with at least one live job).
        tools = Tool.objects.annotate(
            job_count=Count('jobs', filter=Q(jobs__is_active=True))
        ).filter(job_count__gt=0)
        tool_ids = set(tools.values_list('id', flat=True))
        tool_by_id = {t.id: t for t in tools}

        # ONE pass over the live, salaried jobs (plus a single prefetch of their
        # tools) instead of a query-per-tool + query-per-job N+1. Each job's
        # parsed salary is attributed to every in-scope tool it lists.
        agg = {}  # tool_id -> [min_sum, max_sum, count]
        jobs = (
            Job.objects.filter(is_active=True, screening_status='approved')
            .exclude(salary_range__isnull=True).exclude(salary_range='')
            .prefetch_related('tools')
        )
        for job in jobs:
            s_min, s_max = job.get_salary_min_max()
            if not (s_min and s_max):
                continue
            for tool in job.tools.all():  # prefetched — no extra query
                if tool.id not in tool_ids:
                    continue
                bucket = agg.setdefault(tool.id, [0, 0, 0])
                bucket[0] += s_min
                bucket[1] += s_max
                bucket[2] += 1

        salary_stats = [
            {
                'tool': tool_by_id[tid],
                'avg_min': int(b[0] / b[2]),
                'avg_max': int(b[1] / b[2]),
                'count': b[2],
            }
            for tid, b in agg.items() if b[2] > 0
        ]
        salary_stats.sort(key=lambda x: x['avg_max'], reverse=True)
        data = salary_stats
        cache.set('salary_guide_data_v2', data, 3600)

    # Real aggregates computed from the data — no fabricated numbers.
    stack_count = len(data)
    data_points = sum(s['count'] for s in data)
    overall_min_k = (min((s['avg_min'] for s in data), default=0)) // 1000
    overall_max_k = (max((s['avg_max'] for s in data), default=0)) // 1000

    return render(request, 'jobs/salary_guide.html', {
        'salary_stats': data,
        'stack_count': stack_count,
        'data_points': data_points,
        'overall_min_k': overall_min_k,
        'overall_max_k': overall_max_k,
    })

def _salary_stats(jobs):
    """Aggregate real, disclosed salary ranges into honest stats. Returns None
    when no job in the set disclosed pay (we never fabricate a number)."""
    lows, highs, mids = [], [], []
    for j in jobs:
        lo, hi = j.get_salary_min_max()
        if lo and hi:
            lows.append(lo); highs.append(hi); mids.append((lo + hi) // 2)
    n = len(mids)
    if n == 0:
        return None
    mids.sort()

    def pct(p):
        k = max(0, min(n - 1, int(round((p / 100.0) * (n - 1)))))
        return mids[k]

    return {
        'count': n,
        'avg_low': int(sum(lows) / n),
        'avg_high': int(sum(highs) / n),
        'p25': pct(25), 'median': pct(50), 'p75': pct(75),
        'low': min(lows), 'high': max(highs),
    }


def role_salary(request, role_slug):
    """Per-role salary page, e.g. /marketing-operations-manager-salary/.
    Computed entirely from disclosed pay in the live/recent job corpus."""
    cfg = TITLE_JOBS.get(role_slug)
    if not cfg:
        raise Http404("Unknown role")

    q = Q()
    for kw in cfg["kw"]:
        q |= Q(title__icontains=kw)
    jobs = (Job.objects.filter(is_active=True, screening_status="approved")
            .filter(q).prefetch_related("tools").distinct())

    stats = _salary_stats(jobs)
    remote_stats = _salary_stats(jobs.filter(work_arrangement='remote'))
    onsite_stats = _salary_stats(jobs.exclude(work_arrangement='remote'))

    # Top tools among these roles (skills chips) and example roles with pay.
    paired_ids = list(jobs.values_list('id', flat=True))
    top_tools = (
        Tool.objects.filter(jobs__id__in=paired_ids)
        .annotate(c=Count('jobs', filter=Q(jobs__id__in=paired_ids)))
        .order_by('-c').distinct()[:8]
    )
    examples = [j for j in jobs.order_by('-is_pinned', '-created_at')
                if j.get_salary_min_max()[0]][:6]

    return render(request, 'jobs/salary_role.html', {
        'role_slug': role_slug,
        'role_name': cfg["name"],
        'role_intro': cfg.get("intro", ""),
        'stats': stats,
        'remote_stats': remote_stats,
        'onsite_stats': onsite_stats,
        'top_tools': top_tools,
        'examples': examples,
        'total_open': jobs.count(),
        # Thin data => keep it out of the index until it's substantive.
        'page_noindex': (not stats) or stats['count'] < 3,
    })


def _unsubscribe_everywhere(email):
    """Stop ALL recurring mail for an address: the newsletter digest
    (Subscriber soft-delete/suppression) AND any saved-search alerts.
    A one-click unsubscribe must silence every daily send or we violate
    CAN-SPAM / Gmail bulk-sender rules — saved-search-only signups have no
    Subscriber row, so touching only Subscriber left their alerts running.
    Returns total rows deactivated."""
    n = Subscriber.objects.filter(email=email, is_active=True).update(
        is_active=False, unsubscribed_at=timezone.now())
    n += SavedSearch.objects.filter(email=email, is_active=True).update(is_active=False)
    return n


def unsubscribe(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        if email:
            updated = _unsubscribe_everywhere(email)
            if updated > 0: messages.success(request, f"✅ {email} has been unsubscribed.")
            else: messages.warning(request, "⚠️ That email was not found on our active list.")
    return render(request, "jobs/unsubscribe.html")

@csrf_exempt
def unsubscribe_oneclick(request, token):
    """
    RFC 8058 one-click unsubscribe target referenced by the List-Unsubscribe
    header. The token is a signed payload of the email so we can't be tricked
    into unsubscribing arbitrary addresses. Gmail/Apple Mail POST here directly;
    humans clicking the header link arrive via GET.
    """
    from django.core import signing
    try:
        email = signing.loads(token, salt="unsubscribe", max_age=60 * 60 * 24 * 365)
    except signing.BadSignature:
        return render(request, "jobs/unsubscribe.html", {"oneclick_error": True})

    # Suppress the newsletter AND deactivate saved-search alerts — one click
    # must stop every recurring send (see _unsubscribe_everywhere).
    _unsubscribe_everywhere(email)
    # POST (mail-client one-click) just needs a 200; GET shows confirmation.
    if request.method == "POST":
        return HttpResponse("Unsubscribed", status=200)
    messages.success(request, f"✅ {email} has been unsubscribed. Sorry to see you go!")
    return render(request, "jobs/unsubscribe.html", {"oneclick_done": True})

TOOL_TAGLINES = {
    "salesforce": "Salesforce Marketing Cloud, CRM administration, and platform roles — the backbone of enterprise marketing and revenue operations.",
    "hubspot": "HubSpot Marketing Hub, Ops, and automation roles — for the people who run inbound and lifecycle on HubSpot.",
    "marketo": "Marketo campaign, lead-scoring, and marketing-ops roles for demand-gen and automation specialists.",
    "braze": "Braze lifecycle, push, and in-app messaging roles — cross-channel engagement at scale.",
    "adobe": "Adobe Experience Platform, AEP, and AEM roles for enterprise experience and data teams.",
    "klaviyo": "Klaviyo email & SMS roles focused on DTC retention and lifecycle marketing.",
    "segment": "Segment CDP, tracking, and identity roles — the data plumbing behind modern marketing.",
    "snowflake": "Snowflake warehouse, modeling, and BI roles for analytics-engineering and data teams.",
}

def tool_detail(request, slug):
    # 301 mixed-case slugs (e.g. /jobs/Salesforce/) to the canonical lowercase
    # so we don't split equity across two URLs.
    if slug != slug.lower():
        return redirect('tool_detail', slug=slug.lower(), permanent=True)
    tool = get_object_or_404(Tool, slug=slug)

    query = request.GET.get("q", "").strip()
    location_query = request.GET.get("l", "").strip()
    work_arrangement_filter = request.GET.get("arrangement", "").strip().lower()
    sort = request.GET.get("sort", "").strip().lower()

    jobs = Job.objects.filter(
        tools=tool, is_active=True, screening_status='approved'
    ).prefetch_related("tools")

    if query:
        jobs = jobs.filter(Q(title__icontains=query) | Q(company__icontains=query))
    if location_query:
        jobs = jobs.filter(location__icontains=location_query)
    if work_arrangement_filter:
        jobs = jobs.filter(work_arrangement__iexact=work_arrangement_filter)

    if sort == "oldest":
        jobs = jobs.order_by("created_at")
    else:
        jobs = jobs.order_by("-is_pinned", "-created_at")

    jobs = jobs.distinct()
    total_count = jobs.count()

    paginator = Paginator(jobs, 25)
    jobs_page = paginator.get_page(request.GET.get('page'))

    # "Often paired with" — tools that co-occur on the same jobs as this tool.
    paired_job_ids = Job.objects.filter(
        tools=tool, is_active=True, screening_status='approved'
    ).values_list("id", flat=True)
    often_paired = (
        Tool.objects.filter(jobs__id__in=list(paired_job_ids)).exclude(id=tool.id)
        .annotate(pair_count=Count("jobs", filter=Q(jobs__id__in=list(paired_job_ids))))
        .order_by("-pair_count").distinct()[:6]
    )

    params = request.GET.copy()
    params.pop("page", None)
    filter_qs = params.urlencode()

    # Junk/non-canonical tools (ssf, paid-media-data, crm, …) get noindex'd so
    # they stop diluting site quality, even if they carry a few mis-tagged jobs.
    tool_is_canonical = tool.name.lower() in _CANONICAL_TOOL_NAMES
    has_interview_guide = InterviewGuide.objects.filter(slug=tool.slug, is_published=True).exists()
    has_cert_guide = CertificationGuide.objects.filter(slug=tool.slug, is_published=True).exists()
    return render(request, 'jobs/tool_detail.html', {
        'has_interview_guide': has_interview_guide,
        'has_cert_guide': has_cert_guide,
        'tool': tool,
        'jobs': jobs_page,
        'total_count': total_count,
        'page_noindex': (total_count == 0) or (not tool_is_canonical),
        'query': query,
        'location_filter': location_query,
        'current_arrangement': work_arrangement_filter,
        'current_sort': sort,
        'view_mode': request.GET.get("view", "list"),
        'often_paired': often_paired,
        'tool_tagline': tool.description or TOOL_TAGLINES.get(slug, ""),
        'filter_qs': filter_qs,
        'location_name': 'Global/Remote',
        'cross_cities': SEO_CROSS_CITIES, 'cross_states': SEO_CROSS_STATES,
    })

def tool_interview(request, tool_slug):
    """Per-tool interview guide, e.g. /hubspot-interview-questions/. Curated
    question bank + a live data spine (open roles, co-required tools, companies
    hiring) so the page stays fresh and original."""
    if tool_slug != tool_slug.lower():
        return redirect('tool_interview', tool_slug=tool_slug.lower(), permanent=True)

    guide = (InterviewGuide.objects.filter(slug=tool_slug, is_published=True)
             .select_related('tool').first())
    if not guide:
        raise Http404("No interview guide for this tool")
    tool = guide.tool

    live_jobs = Job.objects.filter(
        tools=tool, is_active=True, screening_status='approved'
    ).prefetch_related('tools')
    live_count = live_jobs.count()

    paired_ids = list(live_jobs.values_list('id', flat=True))
    often_paired = (
        Tool.objects.filter(jobs__id__in=paired_ids).exclude(id=tool.id)
        .annotate(pair_count=Count('jobs', filter=Q(jobs__id__in=paired_ids)))
        .order_by('-pair_count').distinct()[:8]
    )
    hiring_companies = list(
        live_jobs.exclude(company='').values_list('company', flat=True).distinct()[:8]
    )
    recent_jobs = live_jobs.order_by('-is_pinned', '-created_at')[:6]
    has_cert_guide = CertificationGuide.objects.filter(slug=tool.slug, is_published=True).exists()

    # Flatten all Q/A across sections for the FAQPage JSON-LD, so the template
    # can emit a clean comma-separated list with no trailing/leading comma bugs
    # even when some sections have no items.
    faq_items = [
        it for sec in (guide.questions or []) for it in sec.get('items', [])
        if it.get('q') and it.get('a')
    ]

    return render(request, 'jobs/interview_guide.html', {
        'guide': guide,
        'tool': tool,
        'live_count': live_count,
        'often_paired': often_paired,
        'hiring_companies': hiring_companies,
        'recent_jobs': recent_jobs,
        'has_cert_guide': has_cert_guide,
        'faq_items': faq_items,
        # Index only once it has real content; thin guides stay out of the index.
        'page_noindex': guide.question_count() < 5,
    })


def tool_certification(request, tool_slug):
    """Per-tool certification guide, e.g. /hubspot-certification/. Curated cert
    content + a live data spine (open roles, companies hiring, paired tools) so
    the page stays fresh."""
    if tool_slug != tool_slug.lower():
        return redirect('tool_certification', tool_slug=tool_slug.lower(), permanent=True)

    guide = (CertificationGuide.objects.filter(slug=tool_slug, is_published=True)
             .select_related('tool').first())
    if not guide:
        raise Http404("No certification guide for this tool")
    tool = guide.tool

    live_jobs = Job.objects.filter(
        tools=tool, is_active=True, screening_status='approved'
    ).prefetch_related('tools')
    live_count = live_jobs.count()

    paired_ids = list(live_jobs.values_list('id', flat=True))
    often_paired = (
        Tool.objects.filter(jobs__id__in=paired_ids).exclude(id=tool.id)
        .annotate(pair_count=Count('jobs', filter=Q(jobs__id__in=paired_ids)))
        .order_by('-pair_count').distinct()[:8]
    )
    hiring_companies = list(
        live_jobs.exclude(company='').values_list('company', flat=True).distinct()[:8]
    )
    top_jobs = live_jobs.order_by('-is_pinned', '-created_at')[:5]
    has_interview_guide = InterviewGuide.objects.filter(slug=tool.slug, is_published=True).exists()

    return render(request, 'jobs/cert_guide.html', {
        'guide': guide,
        'tool': tool,
        'live_count': live_count,
        'often_paired': often_paired,
        'hiring_companies': hiring_companies,
        'top_jobs': top_jobs,
        'has_interview_guide': has_interview_guide,
        # noindex if no study path (thin content)
        'page_noindex': not guide.study_path,
    })


def _related_jobs_for(job, tool_ids, limit=6):
    return (
        Job.objects.filter(is_active=True, screening_status='approved')
        .exclude(id=job.id)
        .filter(Q(tools__id__in=tool_ids) | Q(company=job.company) | Q(function=job.function))
        .prefetch_related('tools')
        .distinct()
        .order_by('-created_at')[:limit]
    )


def job_detail(request, id, slug):
    job = Job.objects.filter(id=id).first()
    if job is None:
        # The URL matched /job/<id>/<slug>/ but the row is gone — this is a
        # listing we ingested, indexed, then purged once expired. Return 410
        # Gone (not 404) so Google de-indexes it promptly and stops wasting
        # crawl budget re-checking it, while still showing the visitor live
        # alternatives instead of a dead end.
        return render(request, 'jobs/job_closed.html', {
            'job': None,
            'related_jobs': Job.objects.filter(
                is_active=True, screening_status='approved'
            ).order_by('-is_pinned', '-created_at')[:6],
        }, status=410)

    tool_ids = list(job.tools.values_list('id', flat=True))

    # Closed/expired role: the row still exists (clean_stale_jobs demotes rather
    # than deletes) but is no longer live. Show a "no longer available → similar
    # roles" page with HTTP 410 Gone (not 200) so Google stops classifying these
    # as Soft 404s and de-indexes them cleanly, while the visitor still gets live
    # alternatives instead of a dead end.
    if not (job.is_active and job.screening_status == 'approved'):
        return render(request, 'jobs/job_closed.html', {
            'job': job,
            'related_jobs': _related_jobs_for(job, tool_ids),
        }, status=410)

    if job.slug and job.slug != slug: return redirect('job_detail', id=job.id, slug=job.slug, permanent=True)

    # Similar jobs: same company / same tools / same function — keeps the
    # session alive instead of dead-ending after the apply CTA.
    related_jobs = _related_jobs_for(job, tool_ids)
    return render(request, 'jobs/job_detail.html', {'job': job, 'related_jobs': related_jobs})

def post_job(request):
    if request.method == 'POST':
        if _rate_limited(request, 'post_job', limit=5, window_seconds=3600):
            return HttpResponse("Too many submissions. Please try again later.", status=429)
        form = JobPostForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            if not job.location: job.location = "Remote"
            plan = form.cleaned_data.get('plan')
            job.plan_name = plan
            job.is_featured = False; job.is_pinned = False; job.screening_status = 'pending'; job.is_active = False 
            job.tags = f"User Submission: {plan}"; job.save(); form.save_m2m()
            
            new_tools_text = form.cleaned_data.get('new_tools')
            if new_tools_text:
                # WHITELIST: only attach tools that resolve to a canonical MarTech
                # tool. Free-text that isn't a recognized tool is dropped — never
                # mint an arbitrary Tool row (that was the source of junk pages).
                tool_category = None
                for name in [t.strip() for t in new_tools_text.split(',') if t.strip()]:
                    canon = resolve_tool_name(name)
                    if not canon:
                        continue
                    tool = (Tool.objects.filter(name__iexact=canon).first()
                            or Tool.objects.filter(slug=slugify(canon)).first())
                    if not tool:
                        if tool_category is None:
                            tool_category, _ = Category.objects.get_or_create(
                                name="MarTech Tools", defaults={'slug': 'martech-tools'})
                        try:
                            tool = Tool.objects.create(name=canon, slug=slugify(canon), category=tool_category)
                        except Exception:
                            tool = Tool.objects.filter(name__iexact=canon).first()
                    if tool:
                        job.tools.add(tool)

            cache.delete('popular_tech_stacks_v4'); cache.delete('available_countries_v2')
            if plan == 'featured':
                if not settings.STRIPE_SECRET_KEY: return HttpResponse("Error: STRIPE_SECRET_KEY missing", status=500)
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{'price_data': {'currency': 'usd', 'unit_amount': 9900, 'product_data': {'name': 'Featured Job Post', 'description': f'Premium listing for {job.title}'}}, 'quantity': 1}],
                    mode='payment', success_url=settings.DOMAIN_URL + f'/post-job/success/?plan=featured&session_id={{CHECKOUT_SESSION_ID}}', cancel_url=settings.DOMAIN_URL + '/post-job/', metadata={'job_id': job.id, 'plan': 'featured'}
                )
                return redirect(checkout_session.url)
            return redirect('/post-job/success/?plan=free')
    else: form = JobPostForm()
    return render(request, 'jobs/post_job.html', {'form': form})

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    # Refuse to process webhooks at all if signature verification isn't configured.
    if not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse(status=500)
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        job_id = session.get('metadata', {}).get('job_id')
        # Only publish the job if Stripe confirms the money actually arrived.
        if job_id and session.get('payment_status') == 'paid':
            try: 
                job = Job.objects.get(id=job_id); job.is_featured = True; job.is_pinned = True; job.screening_status = 'approved'; job.is_active = True; job.save()
                cache.delete('popular_tech_stacks_v4'); cache.delete('available_countries_v2'); send_job_alert(job)
            except Job.DoesNotExist: pass
    return HttpResponse(status=200)

def post_job_success(request): return render(request, 'jobs/post_job_success.html')

def subscribe(request):
    if request.method == "POST":
        if _rate_limited(request, 'subscribe', limit=5, window_seconds=3600):
            return JsonResponse({"success": False, "error": "Too many attempts. Try again later."}, status=429)
        email = request.POST.get("email", "").strip().lower()
        if email:
            try: validate_email(email)
            except ValidationError: return JsonResponse({"success": False, "error": "Invalid email format."}, status=400)

            # If the form carried search context (the "Be first to new X roles"
            # bar), create a targeted SavedSearch alert. Otherwise it's a general
            # newsletter signup -> Subscriber.
            sq = request.POST.get("q", "").strip()[:200]
            stool = request.POST.get("tool", "").strip()[:100]
            sloc = request.POST.get("l", "").strip()[:120]
            sfunc = request.POST.get("function", "").strip().lower()[:20]
            sarr = request.POST.get("arrangement", "").strip().lower()[:20]
            has_filters = any([sq, stool, sloc, sfunc, sarr])

            if has_filters:
                parts = []
                if sfunc: parts.append(sfunc.title())
                if stool: parts.append(stool.replace('-', ' ').title())
                if sq: parts.append(f'"{sq}"')
                if sarr == 'remote': parts.append('Remote')
                if sloc: parts.append(sloc)
                label = " · ".join(parts) or "MarTech jobs"
                # Is this the first time we've ever seen this email? If they
                # already have a saved search or are a confirmed subscriber,
                # they've had a welcome — don't send a second one.
                already_known = (
                    SavedSearch.objects.filter(email=email).exists()
                    or Subscriber.objects.filter(email=email).exists()
                )
                _, newly = SavedSearch.objects.get_or_create(
                    email=email, query=sq, tool=stool, location=sloc,
                    function=sfunc, arrangement=sarr, defaults={'label': label},
                )
                if newly and not already_known:
                    send_welcome_email(email)
                return JsonResponse({"success": True})

            # General newsletter signup -> double opt-in. Hold the email in
            # PendingSubscriber until they click the confirmation link; only
            # then do they become a real (sending-list) Subscriber.
            # Only an ACTIVE subscriber is "already subscribed". A previously
            # unsubscribed (soft-deleted) row must be allowed back through the
            # double opt-in flow, which reactivates it on confirmation.
            if Subscriber.objects.filter(email=email, is_active=True).exists():
                return JsonResponse({"success": True, "message": "You're already subscribed!"})
            pending, _ = PendingSubscriber.objects.update_or_create(
                email=email, defaults={'token': secrets.token_urlsafe(32)})
            send_confirmation_email(email, pending.token)
            return JsonResponse({"success": True, "message": "Almost there — check your inbox to confirm."})
    return JsonResponse({"success": False}, status=400)


def confirm_subscription(request, token):
    """Double opt-in confirmation: promote a PendingSubscriber to Subscriber."""
    pending = PendingSubscriber.objects.filter(token=token).first() if token else None
    if not pending:
        return render(request, 'jobs/subscription_confirmed.html', {'invalid': True})
    email = pending.email
    sub, created = Subscriber.objects.get_or_create(email=email)
    # Re-subscribe after a prior unsubscribe: the user just completed double
    # opt-in again, so it's an explicit re-consent — reactivate the row.
    reactivated = False
    if not created and not sub.is_active:
        sub.is_active = True
        sub.unsubscribed_at = None
        sub.save(update_fields=["is_active", "unsubscribed_at"])
        reactivated = True
    pending.delete()
    if created or reactivated:
        send_welcome_email(email)
        ua = request.META.get('HTTP_USER_AGENT', 'Unknown')
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        ip = xff.split(',')[0] if xff else request.META.get('REMOTE_ADDR')
        send_admin_new_subscriber_alert(email, ua, ip)
    return render(request, 'jobs/subscription_confirmed.html', {'email': email})


@staff_member_required
def review_queue(request):
    status = request.GET.get("status", "pending").strip().lower()
    q = request.GET.get("q", "").strip()
    jobs = Job.objects.all().order_by("-created_at")
    if status in ("pending", "approved", "rejected"): jobs = jobs.filter(screening_status=status)
    if q: jobs = jobs.filter(Q(title__icontains=q) | Q(company__icontains=q))
    paginator = Paginator(jobs, 50)
    jobs_page = paginator.get_page(request.GET.get("page"))
    return render(request, "jobs/review_queue.html", {"jobs": jobs_page, "status": status, "q": q})

@staff_member_required
def review_action(request, job_id, action):
    job = get_object_or_404(Job, id=job_id)
    if action == "approve": 
        if job.screening_status != "approved":
            job.screening_status = "approved"; job.is_active = True; job.screened_at = timezone.now(); job.save()
            cache.delete('popular_tech_stacks_v4'); cache.delete('available_countries_v2'); send_job_alert(job)
    elif action == "reject": job.screening_status = "rejected"; job.is_active = False; job.save()
    elif action == "pending": job.screening_status = "pending"; job.save()
    # Return to the review queue the staffer came from, but only if the Referer
    # is one of our own pages — never follow an attacker-supplied redirect.
    referer = request.META.get("HTTP_REFERER")
    if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(referer)
    return redirect("review_queue")

def about(request): return render(request, 'jobs/about.html')
def for_employers(request):
    base = Job.objects.filter(is_active=True, screening_status='approved')
    ctx = {
        'live_jobs': base.count(),
        'company_count': base.values('company').distinct().count(),
        'stack_count': Tool.objects.filter(jobs__in=base).distinct().count(),
    }
    return render(request, 'jobs/for_employers.html', ctx)
def privacy(request): return render(request, 'jobs/privacy.html')
def terms(request): return render(request, 'jobs/terms.html')

def contact(request):
    if request.method == "POST":
        if _rate_limited(request, 'contact', limit=5, window_seconds=3600):
            messages.error(request, "Too many messages. Please try again later.")
            return redirect("contact")
        form = ContactForm(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data
            reply_to = [cleaned["email"]] if cleaned.get("email") else None
            topic = cleaned.get("subject") or "General feedback"
            recipient = getattr(settings, "CONTACT_EMAIL", "martechjobs@gmail.com")
            body = cleaned["message"]
            if not reply_to:
                body += "\n\n(No email provided — anonymous feedback.)"
            email = EmailMultiAlternatives(subject=f"Feedback: {topic}", body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient], reply_to=reply_to)
            try: email.send(fail_silently=False); messages.success(request, "Thanks for the feedback — it genuinely helps shape what we build next."); return redirect("contact")
            except: messages.error(request, "We couldn't send your message right now. Please try again.")
    else: form = ContactForm()
    return render(request, "jobs/contact.html", {"form": form})

def company_list(request):
    companies = Job.objects.filter(is_active=True, screening_status='approved')\
        .values('company', 'company_logo')\
        .annotate(job_count=Count('id'), last_posted=Max('created_at'))\
        .order_by('-last_posted')
    
    return render(request, 'jobs/company_list.html', {'companies': companies})

def company_detail(request, company_slug):
    company_name = company_slug.replace('-', ' ')
    
    jobs = Job.objects.filter(
        company__iexact=company_name, 
        is_active=True, 
        screening_status='approved'
    ).order_by('-created_at')

    if not jobs:
        return redirect('job_list')

    canonical_job = jobs.first()
    
    return render(request, 'jobs/company_detail.html', {
        'company_name': canonical_job.company,
        'company_logo': canonical_job.company_logo,
        'jobs': jobs,
        'tech_stack': Tool.objects.filter(jobs__in=jobs).distinct()[:5]
    })

def directory(request):
    # "MarTech Jobs by Tool" hub — only tools that have live roles (no thin
    # empty pages), most-popular first.
    tools = (
        Tool.objects.annotate(job_count=Count('jobs', filter=Q(jobs__is_active=True, jobs__screening_status='approved')))
        .filter(job_count__gt=0)
        .order_by('-job_count')
    )
    
    # 50 States Matrix for Programmatic SEO
    states = [
        "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", 
        "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", 
        "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", 
        "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", 
        "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", 
        "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", 
        "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", 
        "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia", 
        "Washington", "West Virginia", "Wisconsin", "Wyoming"
    ]
    
    # Top Metro Areas Matrix for Programmatic SEO
    top_cities = [
        "New York", "San Francisco", "Austin", "Chicago", "Seattle", "Boston", 
        "Los Angeles", "Denver", "Atlanta", "Dallas", "Miami", "Toronto", "London"
    ]
    
    return render(request, 'jobs/directory.html', {
        'tools': tools,
        'tool_count': tools.count(),
        'states': states,
        'top_cities': top_cities,
    })
