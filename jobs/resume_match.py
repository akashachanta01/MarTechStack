"""Resume Match services: resume file parsing + matching a resume against
every live job. Built on the deterministic ats_match engine (no AI, no cost).

- extract_resume_text(): PDF/DOCX -> plain text, in memory (file never kept)
- job_requirements(): each live job's required MarTech terms, cached
- term_demand(): % of live jobs that ask for each term, from the same cache
- best_matches(): a resume's top-scoring live jobs
"""
import io
import logging
import re

from django.core.cache import cache
from django.utils.html import strip_tags

from jobs.ats_match import extract_terms

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_REQS_CACHE_KEY = "resume_match:job_reqs:v1"
_REQS_TTL = 6 * 3600


class ResumeParseError(ValueError):
    """User-facing reason a file could not be read."""


MAX_UNZIPPED_BYTES = 20 * 1024 * 1024   # a real .docx resume unzips to well under 1 MB
MAX_ZIP_RATIO = 100
MAX_EXTRACTED_CHARS = 200_000


def _check_docx_size(data):
    """Refuse "zip bomb" .docx files (tiny download, gigabytes when unpacked)
    BEFORE python-docx unpacks them into memory."""
    import zipfile
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ResumeParseError("We couldn't read that file. Try saving it as a PDF again, or paste the text instead.")
    unpacked = sum(i.file_size for i in zf.infolist())
    packed = max(1, sum(i.compress_size for i in zf.infolist()))
    if unpacked > MAX_UNZIPPED_BYTES or unpacked / packed > MAX_ZIP_RATIO:
        raise ResumeParseError("That Word file is unusually large inside. Please save it as a PDF or paste the text.")


def extract_resume_text(uploaded):
    """Return plain text from an uploaded PDF or DOCX. Raises ResumeParseError."""
    name = (getattr(uploaded, "name", "") or "").lower()
    if getattr(uploaded, "size", 0) > MAX_UPLOAD_BYTES:
        raise ResumeParseError("That file is over 5 MB. Please upload a smaller PDF or Word file.")
    data = uploaded.read(MAX_UPLOAD_BYTES + 1)
    try:
        if name.endswith(".pdf") or data[:5] == b"%PDF-":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text, total = [], 0
            for page in reader.pages[:10]:
                t = page.extract_text() or ""
                total += len(t)
                if total > MAX_EXTRACTED_CHARS:      # a real resume is a few pages
                    raise ResumeParseError("That PDF is far too long to be a resume. Paste your resume text instead.")
                text.append(t)
            text = "\n".join(text)
        elif name.endswith(".docx"):
            import docx
            _check_docx_size(data)
            doc = docx.Document(io.BytesIO(data))
            parts = [p.text for p in doc.paragraphs]
            for table in doc.tables:
                for row in table.rows:
                    parts.append(" | ".join(c.text for c in row.cells))
            text = "\n".join(parts)
        else:
            raise ResumeParseError("Please upload a PDF or Word (.docx) file.")
    except ResumeParseError:
        raise
    except Exception as e:  # corrupt / encrypted / unsupported internals
        logger.warning("Resume parse failed (%s): %s", name[-8:], e)
        raise ResumeParseError("We couldn't read that file. Try saving it as a PDF again, or paste the text instead.")

    text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if len(text) < 200:
        raise ResumeParseError(
            "We couldn't find text in that file — it may be a scanned image. "
            "Paste your resume text instead."
        )
    return text[:15000]


# Visitor requests never analyse job descriptions: a single long JD can take
# seconds, and a cold cache after a deploy once pushed a resume check past the
# 30s worker timeout (Sept 23). Web paths read what the daily cron cached
# (warm_resume_match); until that's complete, demand/matches are simply hidden.
WEB_BUDGET_S = 0.0

_JOB_KEY = "resume_match:job:v1:{id}:{stamp}"
_JOB_TTL = 7 * 86400


def _job_entry(job):
    """One job's required terms, cached per job so work is never lost."""
    stamp = int(job.updated_at.timestamp()) if getattr(job, "updated_at", None) else 0
    key = _JOB_KEY.format(id=job.id, stamp=stamp)
    entry = cache.get(key)
    if entry is None:
        terms = extract_terms(strip_tags(job.description or ""), for_jd=True)
        entry = {
            "id": job.id, "title": job.title, "company": job.company, "slug": job.slug,
            "where": (job.get_work_arrangement_display() if hasattr(job, "get_work_arrangement_display") else "") or (job.location or ""),
            "terms": {c: i["kind"] for c, i in terms.items()},
        }
        cache.set(key, entry, _JOB_TTL)
    return entry, key


def job_requirements(budget_s=None):
    """({job_id: entry}, complete). Every live job's required MarTech terms.

    With budget_s, spends at most that many seconds computing uncached jobs
    (a visitor must never wait on this; per-job results persist, so each call
    makes progress). Without it (daily cron), computes everything."""
    reqs = cache.get(_REQS_CACHE_KEY)
    if reqs is not None:
        return reqs, True
    import time
    from jobs.models import Job
    started = time.monotonic()
    reqs, complete = {}, True
    qs = Job.objects.filter(is_active=True, screening_status="approved").only(
        "id", "title", "company", "slug", "description", "work_arrangement", "location", "updated_at")
    for job in qs.iterator():
        stamp = int(job.updated_at.timestamp()) if job.updated_at else 0
        cached = cache.get(_JOB_KEY.format(id=job.id, stamp=stamp))
        if cached is None:
            if budget_s is not None and time.monotonic() - started >= budget_s:
                complete = False
                continue
            cached, _ = _job_entry(job)
        if cached["terms"]:
            reqs[job.id] = cached
    reqs_clean = reqs
    if complete:
        cache.set(_REQS_CACHE_KEY, reqs_clean, _REQS_TTL)
    return reqs_clean, complete


def term_demand(budget_s=WEB_BUDGET_S):
    """({canon: pct_of_live_jobs_asking}, n_jobs). Real numbers only: returns
    ({}, 0) until every live job has been analysed (never partial percentages)."""
    reqs, complete = job_requirements(budget_s)
    if not complete or not reqs:
        return {}, 0
    n = len(reqs)
    counts = {}
    for r in reqs.values():
        for canon in r["terms"]:
            counts[canon] = counts.get(canon, 0) + 1
    return {c: round(100 * k / n) for c, k in counts.items()}, n


def rank_missing(missing):
    """Attach demand_pct to each missing term and sort most-requested first."""
    demand, n = term_demand()
    if not n:  # demand not ready yet: keep the engine's order, no numbers shown
        return [dict(m, demand_pct=None) for m in missing]
    ranked = [dict(m, demand_pct=demand.get(m["term"], 0)) for m in missing]
    kind_order = {"platform": 0, "skill": 1, "cert": 2}
    ranked.sort(key=lambda m: (-m["demand_pct"], kind_order.get(m["kind"], 3), m["term"]))
    return ranked


def match_label(matched, required):
    if not required:
        return "none"
    pct = matched / required
    if pct >= 0.8:
        return "strong"
    if pct >= 0.5:
        return "good"
    return "stretch"


def best_matches(resume_text, exclude_id=None, limit=3, better_than=None):
    """Top live jobs for this resume by share of required terms covered.
    better_than: only jobs whose coverage ratio is strictly higher (for a
    'stretch' result, 'fits you better' must actually be better)."""
    reqs, complete = job_requirements(budget_s=WEB_BUDGET_S)
    if not complete:
        return []
    have = set(extract_terms(resume_text).keys())
    scored = []
    for jid, r in reqs.items():
        if jid == exclude_id:
            continue
        need = set(r["terms"])
        hit = len(need & have)
        if better_than is not None and hit / len(need) <= better_than:
            continue
        scored.append((hit / len(need), hit, len(need), r))
    scored.sort(key=lambda s: (-s[0], -s[2]))
    return [
        {"id": r["id"], "title": r["title"], "company": r["company"], "slug": r["slug"],
         "where": r["where"], "matched": hit, "required": n, "label": match_label(hit, n)}
        for _, hit, n, r in scored[:limit]
    ]


_PREFERRED_RX = re.compile(r"\b(preferred|nice[- ]to[- ]have|a plus|bonus|ideally|desirable|familiarity)\b", re.I)
_SENT_SPLIT_RX = re.compile(r"(?<=[.!?;])\s+|\n+|\s+[•·▪◦-]\s+")


def _sentences(jd_text):
    return [s.strip(" •·-\t") for s in _SENT_SPLIT_RX.split(jd_text or "") if s and s.strip()]


def annotate_missing(missing, jd_text):
    """Add where the job asks for each missing term (a short quote) and
    whether it reads as required or nice-to-have. Deterministic, no AI."""
    sents = _sentences(jd_text)
    out = []
    for m in missing:
        quote, preferred = "", False
        words = [w.lower() for w in m.get("jd_wording") or [m["term"]]]
        for sent in sents:
            low = sent.lower()
            hit = next((w for w in words if w in low), None)
            if hit:
                i = low.index(hit)
                start = max(0, i - 70)
                end = min(len(sent), i + len(hit) + 90)
                quote = ("…" if start else "") + sent[start:end].strip() + ("…" if end < len(sent) else "")
                preferred = bool(_PREFERRED_RX.search(sent))
                m = dict(m, quote=quote, quote_term=sent[i:i + len(hit)])
                break
        out.append(dict(m, required=not preferred))
    return out


_ACTION_LINE_RX = re.compile(r"^[\s•·▪◦*-]*[A-Z][a-z]+ed\b|^[\s•·▪◦*-]*(Led|Built|Ran|Own|Owned|Managed|Drove|Grew|Launched|Created|Designed|Implemented|Supported|Partnered|Developed)\b")


def lines_needing_numbers(resume_text, limit=3):
    """Up to `limit` achievement-style resume lines that have no number yet
    (the member's own lines, shown back only to them)."""
    from jobs.ats_match import _METRIC_RX
    picks = []
    for line in (resume_text or "").splitlines():
        l = line.strip()
        if 30 <= len(l) <= 220 and not _METRIC_RX.search(l) and _ACTION_LINE_RX.search(l):
            picks.append(l.lstrip("•·▪◦*- ").strip())
        if len(picks) >= limit:
            break
    return picks


def score_all_jobs(resume_text, budget_s=WEB_BUDGET_S):
    """({job_id: {"matched","required","label","missing"}}, complete) for every
    analysed live job. Pure set maths on the cached job requirements."""
    reqs, complete = job_requirements(budget_s)
    have = set(extract_terms(resume_text).keys())
    out = {}
    for jid, r in reqs.items():
        need = r["terms"]
        hit = [t for t in need if t in have]
        out[jid] = {
            "matched": len(hit), "required": len(need),
            "label": match_label(len(hit), len(need)),
            "missing": sorted(t for t in need if t not in have),
            "title": r["title"], "company": r["company"], "slug": r["slug"], "where": r["where"],
        }
    return out, complete


def user_job_scores(user):
    """Cached per member + resume version (30 min). None if no saved resume."""
    from accounts.models import UserResume
    res = UserResume.objects.filter(user=user).only("text", "updated_at").first()
    if not res:
        return None, False
    key = f"resume_match:user:{user.id}:{int(res.updated_at.timestamp())}"
    hit = cache.get(key)
    if hit:
        return hit, True
    scores, complete = score_all_jobs(res.text)
    if complete:
        cache.set(key, scores, 1800)
    return scores, complete
