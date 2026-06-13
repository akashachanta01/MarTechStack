from django.core.cache import cache
from django.db.models import Count
from .models import Tool, Job

def global_seo_data(request):
    """
    Makes 'popular_tech_stacks' and 'available_countries' available 
    on EVERY page of the website (for the footer).
    """
    
    # 1. POPULAR TECH STACKS (deduped by vendor for a diverse footer)
    popular_tech_stacks = cache.get('popular_tech_stacks_v3')
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
            vendor = stack['name'].split()[0].lower() if stack['name'] else ''
            if vendor in seen_vendors:
                continue
            seen_vendors.add(vendor)
            deduped.append(stack)
            if len(deduped) >= 12:
                break
        popular_tech_stacks = deduped
        cache.set('popular_tech_stacks_v3', popular_tech_stacks, 3600)

    # 2. POPULAR LOCATIONS
    available_countries = cache.get('available_countries_v2')
    if available_countries is None:
        raw_locs = Job.objects.filter(is_active=True).values_list('location', flat=True).distinct()
        country_set = set()
        blocklist = ["not specified", "on-site", "latin america", "va de los poblados"]
        
        for loc in raw_locs:
            if not loc: continue
            # Skip generic terms
            if any(r in loc.lower() for r in ['remote', 'anywhere', 'wfh']): continue
            if any(b in loc.lower() for b in blocklist): continue
            
            parts = loc.split(',')
            if len(parts) >= 1:
                country = parts[-1].strip()
                # Basic validation to ensure it's a real country/state name
                if len(country) > 3 and not any(char.isdigit() for char in country): 
                    country_set.add(country)
                    
        available_countries = sorted(list(country_set))
        cache.set('available_countries_v2', available_countries, 3600)

    return {
        'popular_tech_stacks': popular_tech_stacks,
        'available_countries': available_countries
    }
