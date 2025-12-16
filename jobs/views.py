from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.cache import cache
from collections import defaultdict

from .models import Job, Tool, Category, Subscriber 
from .forms import JobPostForm

# --- CONFIGURATION: VENDOR & CATEGORY GROUPING ---
# KEYS must be LOWERCASE for reliable matching.
# VALUES are the Display Name (e.g. 'Adobe').
TOOL_MAPPING = {
    # Salesforce
    'salesforce marketing cloud': 'Salesforce',
    'sfmc': 'Salesforce',
    'salesforce mc': 'Salesforce',
    'marketing cloud': 'Salesforce',
    'pardot': 'Salesforce',
    'marketing cloud account engagement': 'Salesforce',
    'salesforce cdp': 'Salesforce',
    'data cloud': 'Salesforce',
    'salesforce crm': 'Salesforce',
    'salesforce': 'Salesforce',

    # Adobe
    'marketo': 'Adobe',
    'marketo engage': 'Adobe',
    'adobe experience cloud': 'Adobe',
    'adobe experience platform': 'Adobe',
    'aep': 'Adobe',
    'adobe target': 'Adobe',
    'adobe analytics': 'Adobe',
    'adobe campaign': 'Adobe',
    'adobe journey optimizer': 'Adobe',
    'ajo': 'Adobe',
    'magento': 'Adobe',
    'workfront': 'Adobe',
    'adobe': 'Adobe',

    # HubSpot
    'hubspot crm': 'HubSpot',
    'hubspot marketing hub': 'HubSpot',
    'hubspot operations hub': 'HubSpot',
    'hubspot': 'HubSpot',

    # Google
    'google analytics': 'Google',
    'ga4': 'Google',
    'google tag manager': 'Google',
    'gtm': 'Google',
    'google ads': 'Google',
    'dv360': 'Google',
    'looker': 'Google',
    'bigquery': 'Google',

    # Functional Categories
    'twilio segment': 'Data Stack',
    'segment': 'Data Stack',
    'segment.io': 'Data Stack',
    'tealium': 'Data Stack',
    'tealium iq': 'Data Stack',
    'mparticle': 'Data Stack',
    'hightouch': 'Data Stack',
    'census': 'Data Stack',
    'snowflake': 'Data Stack',
    'sql': 'Data Stack',
    'dbt': 'Data Stack',
    'fivetran': 'Data Stack',

    'outreach': 'Sales Tech',
    'salesloft': 'Sales Tech',
    'gong': 'Sales Tech',
    'apollo': 'Sales Tech',
    'zoominfo': 'Sales Tech',

    'braze': 'Automation',
    'iterable': 'Automation',
    'klaviyo': 'Automation',
    'customer.io': 'Automation',
    'eloqua': 'Automation',
    'activecampaign': 'Automation',
    'mailchimp': 'Automation',

    'shopify': 'Commerce',
    'shopify plus': 'Commerce',
    'bigcommerce': 'Commerce',
    'woocommerce': 'Commerce',

    'the trade desk': 'AdTech',
    'stackadapt': 'AdTech',
    'facebook ads': 'AdTech',
    'linkedin ads': 'AdTech',
}

def job_list(request):
    # --- GET Parameters ---
    query = request.GET.get("q", "").strip()
    vendor_query = request.GET.get("vendor", "").strip()  # <--- New Strict Filter
    
    location_query = request.GET.get("l", "").strip()
    tool_filter = request.GET.get("tool", "").strip()
    category_filter = request.GET.get("category", "").strip()
    role_type_filter = request.GET.get("role_type", "").strip()
    remote_filter = request.GET.get("remote", "").strip()

    # --- Base Query ---
    jobs = (
        Job.objects.filter(is_active=True, screening_status="approved")
        .prefetch_related("tools", "tools__category")
        .order_by("-created_at")
    )

    # --- 1. STRICT VENDOR FILTER (Clicking the Card) ---
    if vendor_query:
        # Handling "General / Strategy" (No Tools)
        if vendor_query == "General / Strategy":
            jobs = jobs.filter(tools__isnull=True)
        else:
            # Find all Tool IDs that map to this Vendor
            # We check every tool in the DB to see if it belongs to the requested Vendor
            relevant_tool_ids = []
            all_tools = Tool.objects.all()
            
            for tool in all_tools:
                # Normalize DB name to lowercase
                clean_name = tool.name.lower()
                
                # Check Mapping
                # 1. Direct match in mapping
                # 2. Fallback: If not in mapping, does the name itself match the vendor?
                group = TOOL_MAPPING.get(clean_name, tool.name) 
                
                # Case-insensitive comparison of group vs requested vendor
                if group.lower() == vendor_query.lower():
                    relevant_tool_ids.append(tool.id)
            
            # Filter jobs that have ANY of these tools
            jobs = jobs.filter(tools__id__in=relevant_tool_ids).distinct()

    # --- 2. TEXT SEARCH (User typing in bar) ---
    elif query:
        search_q = (
            Q(title__icontains=query)
            | Q(company__icontains=query)
            | Q(description__icontains=query)
            | Q(tools__name__icontains=query)
        )
        jobs = jobs.filter(search_q).distinct()

    # --- 3. OTHER FILTERS ---
    if location_query:
        if "remote" in location_query.lower():
            jobs = jobs.filter(Q(remote=True) | Q(location__icontains=location_query))
        else:
            jobs = jobs.filter(location__icontains=location_query)

    if tool_filter:
        jobs = jobs.filter(tools__name__iexact=tool_filter)

    if category_filter:
        jobs = jobs.filter(tools__category__name__iexact=category_filter)

    if role_type_filter:
        jobs = jobs.filter(role_type=role_type_filter)

    if remote_filter.lower() in ("true", "1", "yes", "on"):
        jobs = jobs.filter(remote=True)

    # --- Pagination ---
    paginator = Paginator(jobs.distinct(), 25)
    page_number = request.GET.get("page")
    jobs_page = paginator.get_page(page_number)

    # --- ⚡️ CACHED TECH STACK AGGREGATION ---
    popular_tech_stacks = cache.get('popular_tech_stacks')

    if not popular_tech_stacks:
        # 1. Fetch raw pairs: (Tool Name, Job ID)
        pairs = Tool.objects.filter(
            jobs__is_active=True, 
            jobs__screening_status='approved'
        ).values_list('name', 'jobs__id')

        # 2. Aggregation with Strict Lowercase Normalization
        vendor_jobs = defaultdict(set)
        
        for tool_name, job_id in pairs:
            # Normalize to lowercase for lookup
            clean_name = tool_name.lower()
            
            if clean_name in TOOL_MAPPING:
                group_name = TOOL_MAPPING[clean_name]
            else:
                # Fallback: Capitalize properly if it's a standalone tool
                group_name = tool_name # Keep original casing if not mapped
            
            vendor_jobs[group_name].add(job_id)

        # 3. Handle "General / Strategy" (Jobs with NO tools)
        general_jobs_count = Job.objects.filter(
            is_active=True, 
            screening_status='approved',
            tools__isnull=True
        ).count()

        # 4. Convert to List
        stats_list = []
        for group, job_ids in vendor_jobs.items():
            if len(job_ids) > 0:
                stats_list.append({
                    'name': group,
                    'count': len(job_ids),
                    'icon_char': group[0].upper() if group else '?'
                })
        
        if general_jobs_count > 0:
            stats_list.append({
                'name': 'General / Strategy',
                'count': general_jobs_count,
                'icon_char': 'G'
            })

        # 5. Sort
        popular_tech_stacks = sorted(stats_list, key=lambda x: x['count'], reverse=True)[:8]

        # 6. Save to Cache
        cache.set('popular_tech_stacks', popular_tech_stacks, 3600)

    context = {
        "jobs": jobs_page,
        "query": query,
        "vendor_filter": vendor_query, # Pass to template for UI state
        "location_filter": location_query,
        "tool_filter": tool_filter,
        "category_filter": category_filter,
        "role_type_filter": role_type_filter,
        "remote_filter": remote_filter,
        "popular_tech_stacks": popular_tech_stacks,
        "categories": Category.objects.all().order_by("name"),
    }
    return render(request, "jobs/job_list.html", context)


def job_detail(request, job_id):
    job = get_object_or_404(Job, id=job_id, is_active=True, screening_status="approved")
    return render(request, "jobs/job_detail.html", {"job": job})


def post_job(request):
    if request.method == 'POST':
        form = JobPostForm(request.POST, request.FILES)
        if form.is_valid():
            job = form.save(commit=False)
            job.screening_status = 'pending'
            job.is_active = False 
            job.save()
            form.save_m2m()
            cache.delete('popular_tech_stacks') 
            return redirect('post_job_success')
    else:
        form = JobPostForm()
    return render(request, 'jobs/post_job.html', {'form': form})

def post_job_success(request):
    return render(request, 'jobs/post_job_success.html')

def subscribe(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        if email:
            Subscriber.objects.get_or_create(email=email)
    return redirect("job_list")

@staff_member_required
def review_queue(request):
    status = request.GET.get("status", "pending").strip().lower()
    q = request.GET.get("q", "").strip()
    jobs = Job.objects.all().order_by("-created_at")
    if status in ("pending", "approved", "rejected"):
        jobs = jobs.filter(screening_status=status)
    if q:
        jobs = jobs.filter(
            Q(title__icontains=q)
            | Q(company__icontains=q)
            | Q(location__icontains=q)
            | Q(description__icontains=q)
            | Q(apply_url__icontains=q)
        )
    paginator = Paginator(jobs, 50)
    page_number = request.GET.get("page")
    jobs_page = paginator.get_page(page_number)
    return render(request, "jobs/review_queue.html", {"jobs": jobs_page, "status": status, "q": q})

@staff_member_required
def review_action(request, job_id, action):
    job = get_object_or_404(Job, id=job_id)
    if action == "approve":
        job.screening_status = "approved"
        job.is_active = True
        job.screened_at = job.screened_at or timezone.now()
        job.save(update_fields=["screening_status", "is_active", "screened_at"])
        cache.delete('popular_tech_stacks') 
    elif action == "reject":
        job.screening_status = "rejected"
        job.is_active = False
        job.screened_at = job.screened_at or timezone.now()
        job.save(update_fields=["screening_status", "is_active", "screened_at"])
    elif action == "pending":
        job.screening_status = "pending"
        job.save(update_fields=["screening_status"])
    return redirect(request.META.get("HTTP_REFERER", "review_queue"))
