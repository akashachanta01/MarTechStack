"""XML job feed for job search sites (Talent.com, Jooble, Adzuna, Careerjet...).

Oct 2026: Talent.com and Mediabistro were already copying our listings and sending
visitors to our job pages. A standard feed lets them (and others) pick up every
live role reliably. Links point to our job pages, so the visits land here.
"""
from django.core.cache import cache
from django.http import HttpResponse

from .models import Job

DOMAIN = "https://martechjobs.io"
CACHE_KEY = "job_feed_xml_v1"
JOB_TYPES = {"full_time": "full-time", "part_time": "part-time", "contract": "contract",
             "temporary": "temporary", "internship": "internship"}


def _cdata(text):
    return "<![CDATA[" + (text or "").replace("]]>", "]]]]><![CDATA[>") + "]]>"


def build_feed():
    jobs = (Job.objects.filter(is_active=True, screening_status="approved")
            .order_by("-went_live_at", "-created_at"))
    out = ['<?xml version="1.0" encoding="utf-8"?>', "<source>",
           "<publisher>MarTechJobs</publisher>", f"<publisherurl>{DOMAIN}/</publisherurl>"]
    for j in jobs.iterator():
        loc = j.get_address_parts()
        remote = j.work_arrangement == "remote" or "remote" in (j.location or "").lower()
        posted = j.went_live_at or j.created_at
        url = f"{DOMAIN}/job/{j.pk}/{j.slug}/?utm_source=jobfeed&utm_medium=feed"
        out.append("<job>")
        out.append(f"<title>{_cdata(j.title)}</title>")
        out.append(f"<date>{_cdata(posted.strftime('%a, %d %b %Y %H:%M:%S GMT') if posted else '')}</date>")
        out.append(f"<referencenumber>{_cdata(str(j.pk))}</referencenumber>")
        out.append(f"<url>{_cdata(url)}</url>")
        out.append(f"<company>{_cdata(j.company)}</company>")
        out.append(f"<city>{_cdata(loc.get('locality', ''))}</city>")
        out.append(f"<state>{_cdata(loc.get('region', ''))}</state>")
        out.append(f"<country>{_cdata(j.country or '')}</country>")
        out.append(f"<location>{_cdata(j.location or '')}</location>")
        out.append(f"<remotetype>{_cdata('remote' if remote else '')}</remotetype>")
        out.append(f"<jobtype>{_cdata(JOB_TYPES.get(j.role_type, 'full-time'))}</jobtype>")
        if j.salary_range:
            out.append(f"<salary>{_cdata(j.salary_range)}</salary>")
        out.append(f"<description>{_cdata(j.description)}</description>")
        out.append("</job>")
    out.append("</source>")
    return "\n".join(out)


def job_feed_xml(request):
    xml = cache.get(CACHE_KEY)
    if xml is None:
        xml = build_feed()
        cache.set(CACHE_KEY, xml, 3600)
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")
