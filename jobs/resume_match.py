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


def job_requirements():
    """{job_id: {"id","title","company","slug","terms": {canon: kind}}} for
    every live job that asks for at least one MarTech term. Cached 6h."""
    reqs = cache.get(_REQS_CACHE_KEY)
    if reqs is not None:
        return reqs
    from jobs.models import Job
    reqs = {}
    qs = Job.objects.filter(is_active=True, screening_status="approved").only(
        "id", "title", "company", "slug", "description", "work_arrangement", "location")
    for job in qs.iterator():
        terms = extract_terms(strip_tags(job.description or ""), for_jd=True)
        if terms:
            reqs[job.id] = {
                "id": job.id, "title": job.title, "company": job.company, "slug": job.slug,
                "where": (job.get_work_arrangement_display() if hasattr(job, "get_work_arrangement_display") else "") or (job.location or ""),
                "terms": {c: i["kind"] for c, i in terms.items()},
            }
    cache.set(_REQS_CACHE_KEY, reqs, _REQS_TTL)
    return reqs


def term_demand():
    """({canon: pct_of_live_jobs_asking}, n_jobs). Real numbers, never estimated."""
    reqs = job_requirements()
    n = len(reqs)
    counts = {}
    for r in reqs.values():
        for canon in r["terms"]:
            counts[canon] = counts.get(canon, 0) + 1
    return ({c: round(100 * k / n) for c, k in counts.items()} if n else {}), n


def rank_missing(missing):
    """Attach demand_pct to each missing term and sort most-requested first."""
    demand, _ = term_demand()
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
    have = set(extract_terms(resume_text).keys())
    scored = []
    for jid, r in job_requirements().items():
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
