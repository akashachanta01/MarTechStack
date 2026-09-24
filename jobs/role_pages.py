"""Role pages generated from real live job titles (no hand-written copy).

- auto_roles(): normalised job titles ("Senior Salesforce Developer II" ->
  "salesforce developer") that enough live jobs share. Served at /<slug>-jobs/.
- tool_roles(): tool x function combos ("SFMC Developer", "Marketo Specialist")
  from tagged jobs whose title names the function. Served at /jobs/<tool>/<func>/.

A page is indexable (and in the sitemap) only when it has enough live jobs from
enough different employers; below that it is served but noindexed.
"""
import re
from collections import Counter, defaultdict

from django.core.cache import cache
from django.utils.text import slugify

ROLE_SERVE_MIN, ROLE_INDEX_MIN, ROLE_MIN_COMPANIES = 3, 5, 2
COMBO_SERVE_MIN, COMBO_INDEX_MIN, COMBO_MIN_COMPANIES = 2, 3, 2
CACHE_TTL = 6 * 3600

_CUT_RX = re.compile(r"\s(?:-|–|—|\||/)\s|,|:|\s/|/\s")
_BRACKETS_RX = re.compile(r"[\(\[][^\)\]]*[\)\]]")
_ALIASES = {"sfmc": "salesforce marketing cloud", "sfdc": "salesforce", "sr.": "", "martech": "martech"}

# Function words people search with a tool name ("marketo admin jobs").
FUNCTIONS = {
    "developer": ("Developer", r"\bdevelop(er|ment)\b"),
    "architect": ("Architect", r"\barchitect\b"),
    "administrator": ("Admin", r"\badmin(istrator)?\b"),
    "consultant": ("Consultant", r"\bconsult(ant|ing)\b"),
    "engineer": ("Engineer", r"\bengineer\b"),
    "analyst": ("Analyst", r"\banalyst\b"),
    "specialist": ("Specialist", r"\bspecialist\b"),
    "manager": ("Manager", r"\bmanager\b"),
}


_SENIORITY_RX = re.compile(
    r"^(?:(?:senior|sr\.?|lead|principal|staff|junior|jr\.?|associate|intermediate|regional|global|"
    r"freelance|contractor|\(senior\))\s*(?:/\s*)?)+", re.I)
_LEVEL_RX = re.compile(r"\s+(?:i{1,3}|iv|v|[1-5])$")
_PLURAL = {"managers": "manager", "specialists": "specialist", "engineers": "engineer",
           "developers": "developer", "consultants": "consultant", "analysts": "analyst", "architects": "architect"}
_FUNCTION_WORDS = {"developer", "architect", "administrator", "admin", "consultant", "engineer",
                   "analyst", "specialist", "manager", "lead"}


def normalize_title(title):
    """Core role name of a job title, or '' if nothing usable is left.
    "Senior Developer - Salesforce Marketing Cloud" -> "salesforce marketing cloud developer"."""
    t = (title or "").lower().strip()
    t = _BRACKETS_RX.sub(" ", t)
    t = re.sub(r"(\w)-\s", r"\1 ", t)                   # "Salesforce- Technical" -> "Salesforce Technical"
    t = _SENIORITY_RX.sub("", t).strip()
    parts = [p.strip() for p in _CUT_RX.split(t) if p and p.strip()]
    if not parts:
        return ""
    core = parts[0]
    if core in _FUNCTION_WORDS and len(parts) > 1:        # "developer - salesforce marketing cloud"
        core = f"{parts[1]} {core}"
    words = [_ALIASES.get(w.strip("."), w.strip(".")) for w in core.replace("&", " & ").split()]
    words = [_PLURAL.get(w, w) for w in words if w]
    core = _LEVEL_RX.sub("", " ".join(" ".join(words).split()))
    if len(core.split()) < 2 or not re.fullmatch(r"[a-z0-9 &+.'-]+", core):
        return ""
    return core


def _live():
    from jobs.models import Job
    return Job.objects.filter(is_active=True, screening_status="approved")


def auto_roles():
    """{slug: {"name", "ids", "companies", "indexable"}} for shared job titles."""
    data = cache.get("auto_roles:v1")
    if data is not None:
        return data
    from jobs.views import TITLE_JOBS
    groups = defaultdict(list)
    for pk, title, company in _live().values_list("id", "title", "company"):
        core = normalize_title(title)
        if core:
            groups[core].append((pk, company))
    data = {}
    for core, rows in groups.items():
        slug = slugify(core)
        if len(rows) < ROLE_SERVE_MIN or slug in TITLE_JOBS or not slug:
            continue
        companies = {c for _, c in rows}
        data[slug] = {
            "name": " ".join(w.upper() if w in ("aem", "aep", "ajo", "crm", "cdp", "sfmc", "ai", "qa")
                             else w if w == "&" else w.capitalize() for w in core.split()),
            "ids": [pk for pk, _ in rows],
            "companies": len(companies),
            "indexable": len(rows) >= ROLE_INDEX_MIN and len(companies) >= ROLE_MIN_COMPANIES,
        }
    cache.set("auto_roles:v1", data, CACHE_TTL)
    return data


def tool_roles():
    """{(tool_slug, func): {"name", "ids", "companies", "indexable"}}.
    The tool must be named in the job TITLE ("Senior Developer - Salesforce
    Marketing Cloud" is an SFMC Developer; a Marketing Ops Manager who uses SFMC
    is not an "SFMC Manager"). Longest tool name wins, so SFMC titles don't
    also count as plain Salesforce."""
    data = cache.get("tool_roles:v2")
    if data is not None:
        return data
    from jobs.ats_match import extract_terms
    from jobs.models import Tool
    from jobs.tool_catalog import resolve_tool_name
    from jobs.views import TOOL_SHORT_NAMES
    slug_by_name = {t.name.lower(): (t.slug, t.name) for t in Tool.objects.all()}
    rows = defaultdict(list)
    names = {}
    for jid, title, company in _live().values_list("id", "title", "company"):
        t = title or ""
        funcs = [f for f, (_, rx) in FUNCTIONS.items() if re.search(rx, t, re.I)]
        if not funcs:
            continue
        for term, info in extract_terms(t, for_jd=True).items():
            if info.get("kind") != "platform":
                continue
            canon = resolve_tool_name(term)
            hit = slug_by_name.get((canon or "").lower())
            if not hit:
                continue
            tslug, tname = hit
            short = TOOL_SHORT_NAMES.get(tslug, "")
            names[tslug] = short if short.isupper() else tname
            for f in funcs:
                rows[(tslug, f)].append((jid, company))
    data = {}
    for (tslug, func), items in rows.items():
        if len(items) < COMBO_SERVE_MIN:
            continue
        companies = {c for _, c in items}
        data[(tslug, func)] = {
            "name": f"{names[tslug]} {FUNCTIONS[func][0]}",
            "ids": [i for i, _ in items],
            "companies": len(companies),
            "indexable": len(items) >= COMBO_INDEX_MIN and len(companies) >= COMBO_MIN_COMPANIES,
        }
    cache.set("tool_roles:v2", data, CACHE_TTL)
    return data


def facts_intro(name, jobs):
    """One factual sentence from the listings themselves (no generic copy)."""
    jobs = list(jobs)
    if not jobs:
        return f"No open {name} roles right now."
    companies = Counter(j.company for j in jobs)
    remote = sum(1 for j in jobs if j.work_arrangement == "remote")
    top = ", ".join(c for c, _ in companies.most_common(3))
    s = (f"{len(jobs)} open {name} role{'s' if len(jobs) != 1 else ''} at {len(companies)} "
         f"compan{'ies' if len(companies) != 1 else 'y'}, including {top}.")
    if remote:
        s += f" {round(100 * remote / len(jobs))}% are remote."
    return s


def top_platforms(jobs, exclude=(), limit=5):
    c = Counter(t.name for j in jobs for t in j.tools.all() if t.name not in exclude)
    return ", ".join(n for n, _ in c.most_common(limit))
