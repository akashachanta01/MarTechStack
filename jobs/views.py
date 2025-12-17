from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, Value, IntegerField
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.cache import cache
from django.utils.text import slugify
from collections import defaultdict

from .models import Job, Tool, Category, Subscriber 
from .forms import JobPostForm

# [KEEP YOUR EXISTING TOOL_MAPPING HERE - OMITTED FOR BREVITY]
TOOL_MAPPING = {
    'salesforce marketing cloud': 'Salesforce', 'sfmc': 'Salesforce', 'pardot': 'Salesforce',
    'marketo': 'Adobe', 'adobe experience platform': 'Adobe', 'aep': 'Adobe',
    'hubspot': 'HubSpot', 'google analytics': 'Google', 'ga4': 'Google',
    'segment': 'Data Stack', 'tealium': 'Data Stack', 'snowflake': 'Data Stack',
    'outreach': 'Sales Tech', 'salesloft': 'Sales Tech', 'braze': 'Automation',
    'shopify': 'Commerce', 'the trade desk': 'AdTech'
}

def job_list(request):
    # [KEEP EXISTING JOB_LIST CODE UNCHANGED]
    # ... (Copy the exact job_list function from your previous working version)
    query = request.GET.get("q", "").strip()
    vendor_query = request.GET.get("vendor", "").strip() 
    location_query = request.GET.get("l", "").strip()
    work_arrangement_filter = request.GET.get("arrangement", "").strip().lower()

    jobs = Job.objects.filter(is_active=True, screening_status="approved").prefetch_related("tools")

    if vendor_query:
        if vendor_query == "General":
            jobs = jobs.filter(tools__isnull=True)
        else:
            matching_tool_ids = []
            for tool in Tool.objects.all():
                if TOOL_MAPPING.get(tool.name.lower(), tool.name) == vendor_query:
                    matching_tool_ids.append(tool.id)
            jobs = jobs.filter(tools__id__in=matching_tool_ids)
    elif query:
        search_q = Q(title__icontains=query) | Q(company__icontains=query) | Q(tools__name__icontains=query)
        jobs = jobs.filter(search_q).annotate(
            relevance=Case(
                When(title__icontains=query, then=Value(10)),
                When(Q(company__icontains=query) | Q(tools__name__icontains=query), then=Value(5)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
    
    if query:
        jobs = jobs.order_by('-is_pinned', '-relevance', '-created_at')
    else:
        jobs = jobs.order_by('-is_pinned', '-created_at')

    if location_query:
        jobs = jobs.filter(location__icontains=location_query)
    if work_arrangement_filter:
        jobs = jobs.filter(work_arrangement__iexact=work_arrangement_filter)

    paginator = Paginator(jobs.distinct(), 25)
    page_number = request.GET.get("page")
    jobs_page = paginator.get_page(page_number)

    popular_tech_stacks = cache.get('popular_tech_stacks')
    if popular_tech_stacks is None:
        pairs = Tool.objects.filter(jobs__is_active=True, jobs__screening_status='approved').values_list('name', 'jobs__id')
        vendor_jobs = defaultdict(set)
        for tool_name, job_id in pairs:
            clean_name = tool_name.lower()
            group_name = TOOL_MAPPING.get(clean_name, tool_name) 
            vendor_jobs[group_name].add(job_id)

        stats_list = []
        for group, job_ids in vendor_jobs.items():
            if len(job_ids) > 0:
                stats_list.append({'name': group, 'count': len(job_ids)})
        
        popular_tech_stacks = sorted(stats_list, key=lambda x: x['count'], reverse=True)[:10]
        cache.set('popular_tech_stacks', popular_tech_stacks, 3600)

    return render(request, "jobs/job_list.html", {
        "jobs": jobs_page, "query": query, "location_filter": location_query,
        "popular_tech_stacks": popular_tech_stacks, "vendor_filter": vendor_query,
    })

def post_job(request):
    if request.method == 'POST':
        form = JobPostForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            plan = form.cleaned_data.get('plan')
            job.plan_name = plan
            
            # STRATEGY LOGIC:
            if plan == 'featured':
                job.is_featured = True
                job.is_pinned = True
                job.screening_status = 'approved' # Simulating payment success
                job.is_active = True 
            else:
                job.is_featured = False
                job.is_pinned = False
                job.screening_status = 'pending'
                job.is_active = False 
                
            job.tags = f"User Submission: {plan}" 
            job.save()
            
            # Save selected tools (M2M)
            form.save_m2m()
            
            # PROCESS NEW CUSTOM TOOLS
            new_tools_text = form.cleaned_data.get('new_tools')
            if new_tools_text:
                # Get or Create a 'User Submitted' category
                category, _ = Category.objects.get_or_create(name="User Submitted", defaults={'slug': 'user-submitted'})
                
                tool_names = [t.strip() for t in new_tools_text.split(',') if t.strip()]
                for name in tool_names:
                    # Create tool if not exists
                    tool, created = Tool.objects.get_or_create(
                        name__iexact=name, 
                        defaults={'name': name, 'slug': slugify(name), 'category': category}
                    )
                    job.tools.add(tool)

            cache.delete('popular_tech_stacks')
            return redirect('post_job_success')
    else:
        form = JobPostForm()
    return render(request, 'jobs/post_job.html', {'form': form})

# [KEEP OTHER VIEWS: post_job_success, subscribe, review_queue, review_action UNCHANGED]
def post_job_success(request): return render(request, 'jobs/post_job_success.html')
def subscribe(request): 
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        if email: Subscriber.objects.get_or_create(email=email)
    return redirect("job_list")
@staff_member_required
def review_queue(request):
    status = request.GET.get("status", "pending").strip().lower()
    q = request.GET.get("q", "").strip()
    jobs = Job.objects.all().order_by("-created_at")
    if status in ("pending", "approved", "rejected"): jobs = jobs.filter(screening_status=status)
    if q: jobs = jobs.filter(Q(title__icontains=q) | Q(company__icontains=q))
    paginator = Paginator(jobs, 50)
    page_number = request.GET.get("page")
    jobs_page = paginator.get_page(page_number)
    return render(request, "jobs/review_queue.html", {"jobs": jobs_page, "status": status, "q": q})
@staff_member_required
def review_action(request, job_id, action):
    job = get_object_or_404(Job, id=job_id)
    if action == "approve":
        job.screening_status = "approved"; job.is_active = True; job.screened_at = timezone.now(); job.save(); cache.delete('popular_tech_stacks') 
    elif action == "reject":
        job.screening_status = "rejected"; job.is_active = False; job.save()
    elif action == "pending":
        job.screening_status = "pending"; job.save()
    return redirect(request.META.get("HTTP_REFERER", "review_queue"))
