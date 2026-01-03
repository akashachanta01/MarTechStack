from django.core.cache import cache
from django.db.models import Count
from .models import Tool, Job

def global_seo_data(request):
    """
    Makes 'popular_tech_stacks' and 'available_countries' available 
    on EVERY page of the website (for the footer).
    """
    
    # 1. POPULAR TECH STACKS (Top 20 for Footer)
    popular_tech_stacks = cache.get('popular_tech_stacks_v2')
    if popular_tech_stacks is None:
        # We fetch more here (16-20) to fill the footer grid
        popular_tech_stacks = Tool.objects.filter(
            jobs__is_active=True, 
            jobs__screening_status='approved'
        ).values('name', 'slug').annotate(count=Count('jobs')).order_by('-count')[:20]
        cache.set('popular_tech_stacks_v2', list(popular_tech_stacks), 3600)

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
