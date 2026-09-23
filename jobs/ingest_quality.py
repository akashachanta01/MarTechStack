"""Deterministic clean-up rules for ingested job data (site audit batch 2).

Used at ingest (fetch_jobs), on every Job.save(), and by the daily
`clean_job_data` command for rows already in the database. Nothing here
invents data: names come from a reviewed map or the ATS itself, salaries only
from text the employer published in the posting.
"""
import html
import re

# ATS board tokens that are run-together company names ("doordashusa").
# Only names we are sure of; anything else keeps its current name.
COMPANY_NAME_OVERRIDES = {
    "abnormalsecurity": "Abnormal Security",
    "aboutyougmbh": "ABOUT YOU",
    "alphasense": "AlphaSense",
    "alsacstjude": "ALSAC / St. Jude",
    "amerilife": "AmeriLife",
    "astrazeneca": "AstraZeneca",
    "bristolmyerssquibb": "Bristol Myers Squibb",
    "buyersedgeplatformrecruiting": "Buyers Edge Platform",
    "criticalmass": "Critical Mass",
    "cvshealth": "CVS Health",
    "dentsuaegis": "Dentsu",
    "doordashusa": "DoorDash",
    "draftkings": "DraftKings",
    "gevernova": "GE Vernova",
    "gocardless": "GoCardless",
    "hubspotjobs": "HubSpot",
    "la28careers": "LA28",
    "lifestance": "LifeStance Health",
    "marathonhealth": "Marathon Health",
    "mckesson": "McKesson",
    "meowwolf": "Meow Wolf",
    "mxtechnologiesinc": "MX Technologies",
    "neuraflash": "NeuraFlash",
    "onetrust": "OneTrust",
    "phillipsedison": "Phillips Edison & Company",
    "purestorage": "Pure Storage",
    "radiuslimited": "Radius",
    "rockwellautomation": "Rockwell Automation",
    "servicenow": "ServiceNow",
    "smithfieldfoods": "Smithfield Foods",
    "synchronyfinancial": "Synchrony",
    "trendmicro": "Trend Micro",
    "ubisoft2": "Ubisoft",
    "wppmedia": "WPP Media",
    "zooplusse": "zooplus",
}


def display_company(name):
    """Readable company name for a raw ATS token/name ('Doordashusa' -> 'DoorDash')."""
    if not name:
        return name
    return COMPANY_NAME_OVERRIDES.get(name.strip().lower().replace(" ", ""), name)


# Requisition codes in titles: "(PR0056) Salesforce Consultant", "Analyst (L09)".
# A bracketed token with a digit and no spaces; bare years like (2026) are kept.
_REQ_CODE_RX = re.compile(r"\s*[\(\[](?!(?:19|20)\d\d[\)\]])(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{2,12}[\)\]]\s*")


def clean_title(title):
    if not title:
        return title
    cleaned = _REQ_CODE_RX.sub(" ", title)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -–—|,")
    return cleaned or title.strip()


_N_LOCATIONS_RX = re.compile(r"^\s*\d+\s+locations?\s*$", re.I)


def tidy_location(loc):
    """'6 Locations' -> 'Multiple locations'; a 10-city list keeps the first 3 + count."""
    if not loc:
        return loc
    if _N_LOCATIONS_RX.match(loc):
        return "Multiple locations"
    parts = [p.strip() for p in loc.split(";") if p.strip()]
    if len(parts) > 3:
        return "; ".join(parts[:3]) + f" + {len(parts) - 3} more"
    return loc


# Pay published in the posting text, e.g. "$157,000 — $227,000" or "$110K-$140K".
_AMT = r"(\d{2,3}(?:,\d{3})+(?:\.\d+)?|\d{2,3}(?:\.\d+)?\s?[kK])"
_SALARY_RX = re.compile(
    r"(?P<cur>[$£€])\s?" + _AMT + r"\s*(?:USD|GBP|EUR)?\s*(?:-|–|—|to)\s*(?P=cur)?\s?" + _AMT
)
_CURRENCY = {"$": "USD", "£": "GBP", "€": "EUR"}
_HOURLY_RX = re.compile(r"/\s?h(?:ou)?r|per hour|hourly|an hour", re.I)


def _amount(s):
    s = s.replace(",", "").strip()
    if s[-1:] in "kK":
        return float(s[:-1].strip()) * 1000
    return float(s)


def extract_salary(description):
    """Annual pay range stated in the job description, formatted like the ATS
    feeds ('157,000 - 227,000 USD'), or None. Never guesses: hourly rates and
    implausible ranges are ignored."""
    if not description:
        return None
    text = re.sub(r"<[^>]+>", " ", html.unescape(html.unescape(description)))
    text = re.sub(r"\s+", " ", text)
    for m in _SALARY_RX.finditer(text):
        tail = text[m.end():m.end() + 25]
        if _HOURLY_RX.search(tail):
            continue
        lo, hi = _amount(m.group(2)), _amount(m.group(3))
        if 20_000 <= lo <= hi <= 1_500_000 and hi <= lo * 3:
            return f"{int(lo):,} - {int(hi):,} {_CURRENCY[m.group('cur')]}"
    return None
