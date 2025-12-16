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
# We map specific tools to either a VENDOR (Adobe) or a FUNCTION (AdTech).
TOOL_MAPPING = {
    # --- MAJOR VENDORS ---
    # Salesforce
    'Salesforce Marketing Cloud': 'Salesforce',
    'SFMC': 'Salesforce',
    'Salesforce MC': 'Salesforce',
    'Marketing Cloud': 'Salesforce',
    'Pardot': 'Salesforce',
    'Marketing Cloud Account Engagement': 'Salesforce',
    'Salesforce CDP': 'Salesforce',
    'Data Cloud': 'Salesforce',
    'Salesforce CRM': 'Salesforce',
    'Salesforce': 'Salesforce',

    # Adobe
    'Marketo': 'Adobe',
    'Marketo Engage': 'Adobe',
    'Adobe Experience Cloud': 'Adobe',
    'Adobe Experience Platform': 'Adobe',
    'AEP': 'Adobe',
    'Adobe Target': 'Adobe',
    'Adobe Analytics': 'Adobe',
    'Adobe Campaign': 'Adobe',
    'Adobe Journey Optimizer': 'Adobe',
    'AJO': 'Adobe',
    'Magento': 'Adobe',
    'Workfront': 'Adobe',
    'Adobe': 'Adobe',

    # HubSpot
    'HubSpot CRM': 'HubSpot',
    'HubSpot Marketing Hub': 'HubSpot',
    'HubSpot Operations Hub': 'HubSpot',
    'HubSpot': 'HubSpot',

    # Google
    'Google Analytics': 'Google',
    'GA4': 'Google',
    'Google Tag Manager': 'Google',
    'GTM': 'Google',
    'Google Ads': 'Google',
    'DV360': 'Google',
    'Looker': 'Google',
    'BigQuery': 'Google',

    # --- FUNCTIONAL CATEGORIES (Catch-Alls) ---
    
    # 1. Data & CDP (The "Modern Data Stack")
    'Twilio Segment': 'Data Stack',
    'Segment': 'Data Stack',
    'Segment.io': 'Data Stack',
    'Tealium': 'Data Stack',
    'Tealium iQ': 'Data Stack',
    'mParticle': 'Data Stack',
    'Hightouch': 'Data Stack',
    'Census': 'Data Stack',
    'Snowflake': 'Data Stack',
    'SQL': 'Data Stack',
    'dbt': 'Data Stack',
    'Fivetran': 'Data Stack',

    # 2. Sales Tech / Engagement
    'Outreach': 'Sales Tech',
    'Salesloft': 'Sales Tech',
    'Gong': 'Sales Tech',
    'Apollo': 'Sales Tech',
    'ZoomInfo': 'Sales Tech',
    'Clari': 'Sales Tech',

    # 3. Marketing Automation (The "Others")
    'Braze': 'Automation',
    'Iterable': 'Automation',
    'Klaviyo': 'Automation',
    'Customer.io': 'Automation',
    'Eloqua': 'Automation',
    'ActiveCampaign': 'Automation',
    'Mailchimp': 'Automation',

    # 4. Commerce
    'Shopify': 'Commerce',
    'Shopify Plus': 'Commerce',
    'BigCommerce': 'Commerce',
    'WooCommerce': 'Commerce',
    'Stripe': 'Commerce',

    # 5. AdTech
    'The Trade Desk': 'AdTech',
    'StackAdapt': 'AdTech',
    'Facebook Ads': 'AdTech',
    'LinkedIn Ads': 'AdTech',
    'TikTok Ads': 'AdTech',
}

def job_list(request):
    # --- GET Parameters ---
    query = request.GET.get("q", "").strip()
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

    # --- SMART SEARCH LOGIC ---
    if query:
        # 1. Standard text search
        search_q = (
            Q(title__icontains=query)
            | Q(company__icontains=query)
            | Q(description__icontains=query)
        )

        # 2. Vendor/Category Expansion
        # If searching "Data Stack", find jobs with "Segment", "Snowflake", "SQL"...
        child_tools = [child for child, parent in TOOL_MAPPING.items() if parent.lower() == query.lower()]
        
        # Add the query itself (in case they search "Marketo" directly)
        child_tools.append(query)

        # Add OR condition
        search_q |= Q(tools__name__in=child_tools)
        search_q |= Q(tools__name__icontains=query)

        jobs = jobs.filter(search_q).distinct()

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

        # 2. Aggregation with Fallback
        vendor_jobs = defaultdict(set)
        
        for tool_name, job_id in pairs:
            # Check Mapping first
            if tool_name in TOOL_MAPPING:
                group_name = TOOL_MAPPING[tool_name]
            else:
                # Fallback: If it's not mapped, we can group it into "Other"
                # OR just leave it as its own group.
                # Let's leave it as is, so if "Asana" becomes huge, it shows up.
                group_name = tool_name
            
            vendor_jobs[group_name].add(job_id)

        # 3. Convert to List
        stats_list = []
        for group, job_ids in vendor_jobs.items():
            if len(job_ids) > 0:
                stats_list.append({
                    'name': group,
                    'count': len(job_ids),
                    'icon_char': group[0].upper()
                })

        # 4. Sort by Count Descending
        popular_tech_stacks = sorted(stats_list, key=lambda x: x['count'], reverse=True)[:8]

        # 5. Save to Cache
        cache.set('popular_tech_stacks', popular_tech_stacks, 3600)

    context = {
        "jobs": jobs_page,
        "query": query,
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
