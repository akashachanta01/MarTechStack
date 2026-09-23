"""Resume Match services: resume file parsing + matching a resume against
every live job. Built on the deterministic ats_match engine (no AI, no cost).

- extract_resume_text(): PDF/DOCX -> plain text, in memory (file never kept)
- job_requirements(): each live job's required MarTech terms, cached
- term_demand(): % of live jobs that ask for each term, from the same cache
- best_matches(): a resume's top-scoring live jobs
"""
import io
import logging

from django.core.cache import cache
from django.utils.html import strip_tags

from jobs.ats_match import extract_terms

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_REQS_CACHE_KEY = "resume_match:job_reqs:v1"
_REQS_TTL = 6 * 3600


class ResumeParseError(ValueError):
    """User-facing reason a file could not be read."""


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
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:10])
        elif name.endswith(".docx"):
            import docx
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
            if budget_s is not None and time.monotonic() - started > budget_s:
                complete = False
                continue
            cached, _ = _job_entry(job)
        if cached["terms"]:
            reqs[job.id] = cached
    reqs_clean = reqs
    if complete:
        cache.set(_REQS_CACHE_KEY, reqs_clean, _REQS_TTL)
    return reqs_clean, complete


def term_demand(budget_s=2.0):
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


def best_matches(resume_text, exclude_id=None, limit=3):
    """Top live jobs for this resume by share of required terms covered."""
    reqs, complete = job_requirements(budget_s=2.0)
    if not complete:
        return []
    have = set(extract_terms(resume_text).keys())
    scored = []
    for jid, r in reqs.items():
        if jid == exclude_id:
            continue
        need = set(r["terms"])
        hit = len(need & have)
        scored.append((hit / len(need), hit, len(need), r))
    scored.sort(key=lambda s: (-s[0], -s[2]))
    return [
        {"id": r["id"], "title": r["title"], "company": r["company"], "slug": r["slug"],
         "where": r["where"], "matched": hit, "required": n, "label": match_label(hit, n)}
        for _, hit, n, r in scored[:limit]
    ]
