from django.core.cache import cache
from django.db.models import Count
from .models import Tool, Job

# Query params that produce a filtered/sorted/thin variant of a page. When any
# are present we noindex the page (follow, so equity still flows) and canonical
# back to the clean URL — prevents duplicate-content / crawl-budget bloat.
FILTER_PARAMS = {
    'q', 'l', 'tool', 'arrangement', 'sort', 'rtype', 'view',
    'vendor', 'country', 'function', 'all', 'category', 'status',
}


COUNTRIES_CACHE_KEY = 'available_countries_v4'


def seo_indexing(request):
    """
    Per-request canonical URL + robots directive for clean indexing:
      - filtered/search/sort URLs  -> noindex,follow + canonical to clean path
      - paginated URLs (?page=N>1) -> index,follow + SELF-referencing canonical
        (so deep listing pages get indexed instead of folding to page 1)
      - clean URLs                 -> index,follow + canonical to path
    """
    base = f"https://martechjobs.io{request.path}"
    params = set(request.GET.keys())
    page = request.GET.get('page', '')

    if params & FILTER_PARAMS:
        return {'canonical_url': base, 'robots_directive': 'noindex, follow'}

    if page.isdigit() and int(page) > 1:
        return {'canonical_url': f"{base}?page={page}", 'robots_directive': 'index, follow'}

    return {'canonical_url': base, 'robots_directive': 'index, follow'}


def global_seo_data(request):
    """
    Makes 'popular_tech_stacks' and 'available_countries' available
    on EVERY page of the website (for the footer).
    """

    # 1. POPULAR TECH STACKS (deduped by vendor for a diverse footer)
    popular_tech_stacks = cache.get('popular_tech_stacks_v4')
    if popular_tech_stacks is None:
        raw_stacks = Tool.objects.filter(
            jobs__is_active=True,
            jobs__screening_status='approved'
        ).values('name', 'slug').annotate(count=Count('jobs')).order_by('-count')[:40]

        # Keep only the top stack per vendor family (first word of the name)
        # so the footer isn't dominated by e.g. 5 Adobe / 4 Salesforce products.
        seen_vendors = set()
        deduped = []
        for stack in raw_stacks:
            name = stack['name'] or ''
            # Skip junk auto-created tools: multi-word, all-lowercase names
            # (e.g. "paid media data") are almost always noise. Real tools are
            # capitalized ("Salesforce") or single-word lowercase ("dbt").
            if ' ' in name and name == name.lower():
                continue
            vendor = name.split()[0].lower() if name else ''
            if vendor in seen_vendors:
                continue
            seen_vendors.add(vendor)
            deduped.append(stack)
            if len(deduped) >= 12:
                break
        popular_tech_stacks = deduped
        cache.set('popular_tech_stacks_v4', popular_tech_stacks, 3600)

    # 2. LOCATION DROPDOWN: countries only (from the structured country field),
    # with live job counts, busiest first.
    available_countries = cache.get(COUNTRIES_CACHE_KEY)
    if available_countries is None:
        from jobs.geo import country_name
        rows = (Job.objects.filter(is_active=True, screening_status='approved').exclude(country='')
                .values('country').annotate(n=Count('id')).order_by('-n'))
        available_countries = [{"name": country_name(r['country']), "count": r['n']}
                               for r in rows if country_name(r['country'])]
        cache.set(COUNTRIES_CACHE_KEY, available_countries, 3600)

    return {
        'popular_tech_stacks': popular_tech_stacks,
        'available_countries': available_countries
    }
