"""MarTech Hiring Report: monthly, citable numbers computed from live listings.

compute_report() is the single source for /martech-job-market-statistics/ and for the
monthly HiringSnapshot rows (saved daily by snapshot_hiring_report) that power the
'change vs last month' columns. Every number is counted from real live jobs."""
import re
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

COUNTRY_NAMES = {
    'US': 'United States', 'GB': 'United Kingdom', 'IN': 'India', 'CA': 'Canada',
    'DE': 'Germany', 'FR': 'France', 'NL': 'Netherlands', 'SG': 'Singapore',
    'AE': 'United Arab Emirates', 'AU': 'Australia', 'IE': 'Ireland', 'ES': 'Spain',
    'CN': 'China', 'HK': 'Hong Kong', 'PL': 'Poland', 'PT': 'Portugal',
    'IT': 'Italy', 'SE': 'Sweden', 'MX': 'Mexico', 'BR': 'Brazil',
}
FUNCTION_LABELS = {'operations': 'Marketing Operations', 'engineering': 'MarTech Engineering',
                   'data': 'Marketing Analytics & Data', 'other': 'Other'}
SENIORITY = [  # first match wins
    ('Director, Head of or VP', re.compile(r"\b(director|head of|vp|vice president|chief)\b", re.I)),
    ('Senior, Lead or Principal', re.compile(r"\b(senior|sr\.?|lead|principal|staff)\b", re.I)),
    ('Manager', re.compile(r"\bmanager\b", re.I)),
]
OTHER_LEVEL = 'Specialist, Analyst or Associate'


def seniority(title):
    for label, rx in SENIORITY:
        if rx.search(title or ''):
            return label
    return OTHER_LEVEL


def pct(n, total):
    return round(n * 100 / total) if total else 0


def compute_report():
    from .models import Job, Tool
    from .tool_catalog import all_canonical_names

    live = Job.objects.filter(is_active=True, screening_status='approved')
    total = live.count()
    remote = live.filter(work_arrangement='remote').count()
    hybrid = live.filter(work_arrangement='hybrid').count()
    new_30 = live.filter(created_at__gte=timezone.now() - timedelta(days=30)).count()

    canonical = {n.lower() for n in all_canonical_names()}
    tools = (Tool.objects.annotate(n=Count('jobs', filter=Q(jobs__is_active=True, jobs__screening_status='approved')))
             .filter(n__gt=0).order_by('-n'))
    by_tool = [(t.name, t.n, pct(t.n, total)) for t in tools if (t.name or '').lower() in canonical][:15]

    by_function = [(FUNCTION_LABELS.get(r['function'], r['function']), r['n'], pct(r['n'], total))
                   for r in live.values('function').annotate(n=Count('id')).order_by('-n')]

    country_counts, level_counts = {}, {}
    for job in live.only('country', 'location', 'title'):
        code = job.get_schema_country()
        country_counts[code] = country_counts.get(code, 0) + 1
        lv = seniority(job.title)
        level_counts[lv] = level_counts.get(lv, 0) + 1
    by_country = sorted(((COUNTRY_NAMES.get(c, c), n, pct(n, total)) for c, n in country_counts.items()),
                        key=lambda x: -x[1])[:10]
    order = [s[0] for s in SENIORITY] + [OTHER_LEVEL]
    by_level = [(lv, level_counts.get(lv, 0), pct(level_counts.get(lv, 0), total)) for lv in order]

    top_companies = [(r['company'], r['n']) for r in
                     live.exclude(company='').values('company').annotate(n=Count('id')).order_by('-n', 'company')[:10]]

    sal_mins, sal_maxes = [], []
    for job in live.exclude(salary_range__isnull=True).exclude(salary_range=''):
        mn, mx = (job.get_salary_min_max() or (None, None))
        if mn and mx and mn > 10000:  # ignore hourly/garbage parses
            sal_mins.append(mn); sal_maxes.append(mx)
    with_salary = len(sal_mins)

    return {
        'total': total,
        'remote': remote,
        'remote_pct': pct(remote, total),
        'hybrid': hybrid,
        'new_30': new_30,
        'companies': live.values('company').distinct().count(),
        'by_tool': by_tool,
        'by_function': by_function,
        'by_country': by_country,
        'by_level': by_level,
        'top_companies': top_companies,
        'with_salary': with_salary,
        'salary_pct': pct(with_salary, total),
        'median_min': sorted(sal_mins)[with_salary // 2] if with_salary else None,
        'median_max': sorted(sal_maxes)[with_salary // 2] if with_salary else None,
    }


def month_start(d=None):
    d = d or timezone.now().date()
    return d.replace(day=1)


def previous_snapshot():
    """Last month's saved numbers, or None (no fake comparisons before we have data)."""
    from .models import HiringSnapshot
    prev = (month_start() - timedelta(days=1)).replace(day=1)
    snap = HiringSnapshot.objects.filter(month=prev).first()
    return snap.data if snap else None


def with_changes(data, prev):
    """Add 'change vs last month' to headline numbers and platform rows when last month exists."""
    out = dict(data)
    out['has_prev'] = bool(prev)
    if not prev:
        out['by_tool'] = [(n, c, p, None) for n, c, p in data['by_tool']]
        return out
    for key in ('total', 'companies', 'remote_pct', 'salary_pct'):
        out[key + '_change'] = data[key] - (prev.get(key) or 0)
    prev_tools = {row[0]: row[1] for row in prev.get('by_tool', [])}
    out['by_tool'] = [(n, c, p, (c - prev_tools[n]) if n in prev_tools else None) for n, c, p in data['by_tool']]
    return out


def key_findings(d):
    """Plain sentences built only from the numbers above (for the page and for pitches)."""
    f = []
    if not d['total']:
        return f
    if d['by_tool']:
        t = d['by_tool'][0]
        f.append(f"{t[0]} is named in {t[2]}% of live MarTech jobs ({t[1]} of {d['total']}), more than any other platform.")
    senior = sum(n for lv, n, _ in d['by_level'] if lv != OTHER_LEVEL and lv != 'Manager')
    f.append(f"{pct(senior, d['total'])}% of roles are senior, lead or director level.")
    f.append(f"{d['remote_pct']}% are fully remote and {pct(d['hybrid'], d['total'])}% hybrid.")
    f.append(f"Only {d['salary_pct']}% of listings publish a salary range.")
    if d['by_country']:
        c = d['by_country'][0]
        f.append(f"{c[0]} has the most openings: {c[1]} ({c[2]}%).")
    return f
