"""
MarTech ATS Match — deterministic resume-vs-job-description keyword matching.

Why deterministic: ATS keyword screening is literal string matching, so plain
code reproduces what a real ATS does, costs nothing per run, and never invents
results. AI is used elsewhere only for optional rewrite tips.

Taxonomy = MarTech platforms (from tool_catalog) + MarTech skills + certs, each
with aliases. The same canonical term can be written many ways ("Pardot" vs
"Account Engagement"); ATS software often only matches the JD's exact wording,
so we flag those "alias fixes" separately from truly missing terms.
"""

import re

from .tool_catalog import _CATALOG

# --- Non-tool MarTech skills: canonical -> aliases -------------------------
_SKILLS = {
    "Marketing Automation": ["marketing automation platform", "map administration"],
    "Lead Scoring": ["lead score", "scoring model", "behavioral scoring"],
    "Lead Routing": ["lead assignment", "lead distribution"],
    "Lead Management": ["lead lifecycle management", "lead lifecycle"],
    "Lifecycle Marketing": ["lifecycle stages", "customer lifecycle"],
    "Nurture Programs": ["nurture", "nurture streams", "nurture campaigns", "drip campaigns", "engagement programs"],
    "Segmentation": ["audience segmentation", "segmentation strategy"],
    "Attribution": ["multi-touch attribution", "attribution modeling", "attribution model"],
    "Email Deliverability": ["deliverability", "email authentication", "dmarc", "dkim"],
    "A/B Testing": ["ab testing", "a/b tests", "split testing", "multivariate testing"],
    "Campaign Operations": ["campaign ops", "campaign execution", "campaign builds"],
    "Data Hygiene": ["data quality", "data governance", "deduplication", "data normalization"],
    "SQL": [],
    "Python": [],
    "APIs & Integrations": ["api integrations", "rest api", "apis", "webhooks", "system integrations"],
    "Customer Data Platform": ["cdp", "customer data platforms"],
    "Personalization": ["dynamic content", "1:1 personalization"],
    "UTM Tracking": ["utm", "utm parameters", "campaign tracking"],
    "Reporting & Dashboards": ["dashboards", "marketing reporting", "performance reporting"],
    "Tag Management": ["tagging", "tag implementation"],
    "Account-Based Marketing": ["abm", "account based marketing"],
    "Revenue Operations": ["revops", "rev ops"],
    "Salesforce Administration": ["sfdc administration"],
    "Email Marketing": ["email campaigns", "email programs"],
    "Journey Orchestration": ["customer journeys", "journey builder", "journey orchestration"],
}

# --- Certifications: canonical -> aliases -----------------------------------
_CERTS = {
    "Marketo Certified Expert": ["marketo certified", "marketo certification", "mce certification", "adobe certified expert marketo"],
    "Salesforce Certified Administrator": ["salesforce admin certification", "salesforce certified admin", "salesforce administrator certification"],
    "Marketing Cloud Email Specialist": ["marketing cloud email specialist", "sfmc email specialist"],
    "Marketing Cloud Administrator": ["marketing cloud admin certification", "sfmc administrator certification"],
    "Account Engagement Specialist": ["pardot specialist", "pardot certified", "account engagement specialist"],
    "HubSpot Certification": ["hubspot certified", "hubspot marketing software certification", "hubspot inbound certification"],
    "Google Analytics Certification": ["gaiq", "google analytics certified", "google analytics individual qualification"],
}

# Aliases that are ordinary English words (or collide with other meanings).
# In JDs these only count if written with product capitalization; "gtm" is
# skipped in JDs entirely because it usually means go-to-market.
_AMBIGUOUS_CANONICALS = {"Segment", "Drift", "Census", "Heap", "Outreach", "Apollo", "Tray.io", "Looker", "Intercom", "Optimizely", "Tableau"}
_JD_SKIP_ALIASES = {"gtm", "tray", "apis", "utm", "nurture", "tagging", "dashboards", "deliverability", "personalization", "segmentation"}


def _build(entries, kind):
    """-> list of (canonical, kind, [variant strings])."""
    out = []
    for canon, aliases in entries.items():
        variants = [canon] + list(aliases)
        out.append((canon, kind, variants))
    return out


_TERMS = _build(_CATALOG, "platform") + _build(_SKILLS, "skill") + _build(_CERTS, "cert")


def _variant_regex(variant):
    # Word-boundary-ish match that tolerates punctuation in names (Tray.io,
    # A/B Testing, Customer.io) and plurals/possessives after the term.
    esc = re.escape(variant)
    return re.compile(r"(?<![A-Za-z0-9])" + esc + r"(?:s|'s)?(?![A-Za-z0-9])", re.IGNORECASE)


_COMPILED = [
    (canon, kind, [(v, _variant_regex(v)) for v in variants])
    for canon, kind, variants in _TERMS
]


def _is_sales_qualified_lead(text, m, hit):
    """In MarTech, 'SQL' is very often Sales Qualified Lead, not the database
    language: 'SQLs', 'MQL-to-SQL', 'MQL to SQL', 'SQL conversion'."""
    if hit.lower().endswith(("s", "'s")) and hit.lower() != "sql":
        return True
    before = text[max(0, m.start() - 12):m.start()].lower()
    after = text[m.end():m.end() + 15].lower()
    return "mql" in before or after.lstrip(" -").startswith(("conversion", "rate", "pipeline", "stage"))


def extract_terms(text, for_jd=False):
    """Return {canonical: {"kind": ..., "found_as": set(variant texts)}}.

    Longest match wins: "Salesforce Marketing Cloud" counts as SFMC only, not
    also as "Salesforce", and "Marketing Cloud Account Engagement" as Pardot,
    not SFMC.
    """
    text = text or ""
    hits = []  # (start, end, canon, kind, variant)
    for canon, kind, variants in _COMPILED:
        for variant, rx in variants:
            if for_jd and variant.lower() in _JD_SKIP_ALIASES:
                continue
            for m in rx.finditer(text):
                hit = m.group(0)
                if for_jd and canon in _AMBIGUOUS_CANONICALS and not hit[:1].isupper():
                    continue  # "community outreach" is not the Outreach tool
                if canon == "SQL" and _is_sales_qualified_lead(text, m, hit):
                    continue  # "SQLs" / "MQL-to-SQL" = sales-qualified leads
                hits.append((m.start(), m.end(), canon, kind, hit))

    hits.sort(key=lambda h: (-(h[1] - h[0]), h[0]))
    taken = []
    found = {}
    for start, end, canon, kind, variant in hits:
        if any(start < t_end and end > t_start for t_start, t_end in taken):
            continue
        taken.append((start, end))
        entry = found.setdefault(canon, {"kind": kind, "found_as": set()})
        # variant = the literal text as written; drop possessives for display.
        entry["found_as"].add(re.sub(r"'s$", "", variant.strip()))
    return found


_METRIC_RX = re.compile(r"(\d+(\.\d+)?\s?%|\$\s?\d|\d+\s?(k|m|mm|million|x)\b|\b\d{2,}\b)", re.IGNORECASE)


def count_quantified_lines(resume_text):
    lines = [l.strip() for l in (resume_text or "").splitlines() if len(l.strip()) > 25]
    quantified = [l for l in lines if _METRIC_RX.search(l)]
    return len(quantified), len(lines)


def match(resume_text, jd_text):
    """Compare a resume to a JD. Pure function, no I/O."""
    required = extract_terms(jd_text, for_jd=True)
    have = extract_terms(resume_text)

    matched, missing, alias_fixes = [], [], []
    for canon, info in sorted(required.items(), key=lambda kv: (kv[1]["kind"], kv[0])):
        jd_words = {v.lower() for v in info["found_as"]}
        if canon in have:
            matched.append({"term": canon, "kind": info["kind"]})
            resume_words = {v.lower() for v in have[canon]["found_as"]}
            # Wording fixes only where naming matters (product rebrands, cert
            # names). Skill phrasing variants are too noisy to be advice.
            if info["kind"] in ("platform", "cert") and not (jd_words & resume_words):
                # Same thing, different wording — literal ATS may not connect them.
                alias_fixes.append({
                    "term": canon,
                    "you_wrote": sorted(have[canon]["found_as"])[0],
                    "jd_says": sorted(info["found_as"])[0],
                })
        else:
            missing.append({"term": canon, "kind": info["kind"]})

    quantified, total_lines = count_quantified_lines(resume_text)
    return {
        "required_count": len(required),
        "matched_count": len(matched),
        "matched": matched,
        "missing": missing,
        "alias_fixes": alias_fixes,
        "quantified_lines": quantified,
        "total_lines": total_lines,
    }
