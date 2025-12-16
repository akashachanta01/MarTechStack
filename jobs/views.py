from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, Value, IntegerField # <--- Added Ranking Tools
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.cache import cache
from collections import defaultdict

from .models import Job, Tool, Category, Subscriber 
from .forms import JobPostForm

# --- CONFIGURATION: VENDOR & CATEGORY GROUPING ---
# KEYS must be LOWERCASE for reliable matching.
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
    vendor_query = request.GET.get("vendor", "").strip() 
    
    location_query = request.GET.get("l", "").strip()
    tool_filter = request.GET.get("tool", "").strip()
    category_filter = request.GET.get("category", "").strip()
    role_type_filter = request.GET.get("role_type", "").strip()
    remote_filter = request.GET.get("remote", "").strip()

    # --- Base Query ---
    jobs = (
        Job.objects.filter(is_active=True, screening_status="approved")
        .prefetch_related("tools", "tools__category")
    )

    # --- 1. STRICT VENDOR FILTER ---
    if vendor_query:
        if vendor_query == "General":
            jobs = jobs.filter(tools__isnull=True).order_by("-created_at")
        else:
            relevant_tool_ids = []
            all_tools = Tool.objects.all()
            for tool in all_tools:
                clean_name = tool.name.lower()
                group = TOOL_MAPPING.get(clean_name, tool.name) 
                if group.lower() == vendor_query.lower():
                    relevant_tool_ids.append(tool.id)
            jobs = jobs.filter(tools__id__in=relevant_tool_ids).distinct().order_by("-created_at")

    # --- 2. ENHANCED TEXT SEARCH ---
    elif query:
        # A. Basic Text Search
        search_q = (
            Q(title__icontains=query)
            | Q(company__icontains=query)
            | Q(description__icontains=query)
            | Q(tools__name__icontains=query)
        )

        # B. Smart Vendor Expansion (The Enhancement)
        # If user types "Adobe", we want to find jobs tagged "Marketo" too.
        query_lower = query.lower()
        matching_tool_ids = []
        
        # Iterate all tools to find which ones map to this query (if query is a vendor)
        all_tools = Tool.objects.all()
        for tool in all_tools:
            t_name_lower = tool.name.lower()
            vendor = TOOL_MAPPING.get(t_name_lower, tool.name).lower()
            if vendor == query_lower:
                matching_tool_ids.append(tool.id)
        
        if matching_tool_ids:
            search_q |= Q(tools__id__in=matching_tool_ids)

        jobs = jobs.filter(search_q).distinct()

        # C. Relevance Ranking (The Score)
        # Title Matches = 10pts
        # Tool/Company Matches = 5pts
        # Description Matches = 1pt
        jobs = jobs.annotate(
            relevance=Case(
                When(title__icontains=query, then=Value(10)),
                When(tools__name__icontains=query, then=Value(5)),
                When(company__icontains=query, then=Value(5)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by('-relevance', '-created_at') # Sort by Score, then Date

    # Default sort if no search
    else:
        jobs = jobs.order_by("-created_at")

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
        pairs = Tool.objects.filter(
            jobs__is_active=True, 
            jobs__screening_status='approved'
        ).values_list('name', 'jobs__id')

        vendor_jobs = defaultdict(set)
        
        for tool_name, job_id in pairs:
            clean_name = tool_name.lower()
            if clean_name in TOOL_MAPPING:
                group_name = TOOL_MAPPING[clean_name]
            else:
                group_name = tool_name 
            
            vendor_jobs[group_name].add(job_id)

        general_jobs_count = Job.objects.filter(
            is_active=True, 
            screening_status='approved',
            tools__isnull=True
        ).count()

        stats_list = []
        for group, job_ids in vendor_jobs.items():
            if len(job_ids) > 0:
                stats_list.append({
                    'name': group,
                    'count': len(job_ids)
                })
        
        if general_jobs_count > 0:
            stats_list.append({
                'name': 'General',
                'count': general_jobs_count
            })

        popular_tech_stacks = sorted(stats_list, key=lambda x: x['count'], reverse=True)[:10]
        cache.set('popular_tech_stacks', popular_tech_stacks, 3600)

    context = {
        "jobs": jobs_page,
        "query": query,
        "vendor_filter": vendor_query,
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
            # CTO UPDATE: Immediate Approval + Tagging
            job.screening_status = 'approved' 
            job.is_active = True 
            job.tags = "User Submission" 
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
