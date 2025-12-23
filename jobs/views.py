import stripe
import json
import os
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, Value, IntegerField
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.cache import cache
from django.utils.text import slugify
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from collections import defaultdict

from .models import Job, Tool, Category, Subscriber 
from .forms import JobPostForm
from .emails import send_job_alert, send_welcome_email

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# [KEEP EXISTING TOOL_MAPPING]
TOOL_MAPPING = {
    'salesforce marketing cloud': 'Salesforce', 'sfmc': 'Salesforce', 'pardot': 'Salesforce',
    'marketo': 'Adobe', 'adobe experience platform': 'Adobe', 'aep': 'Adobe',
    'hubspot': 'HubSpot', 'google analytics': 'Google', 'ga4': 'Google',
    'segment': 'Data Stack', 'tealium': 'Data Stack', 'snowflake': 'Data Stack',
    'outreach': 'Sales Tech', 'salesloft': 'Sales Tech', 'braze': 'Automation',
    'shopify': 'Commerce', 'the trade desk': 'AdTech'
}

def job_list(request):
    # [KEEP EXISTING JOB_LIST LOGIC]
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

# --- NEW SEO VIEW: TOOL DETAIL ---
def tool_detail(request, slug):
    tool = get_object_or_404(Tool, slug=slug)
    
    # Fetch active jobs for this specific tool
    jobs = Job.objects.filter(
        tools=tool, 
        is_active=True, 
        screening_status='approved'
    ).order_by('-is_pinned', '-created_at')

    paginator = Paginator(jobs, 20)
    page_number = request.GET.get('page')
    jobs_page = paginator.get_page(page_number)

    return render(request, 'jobs/tool_detail.html', {
        'tool': tool,
        'jobs': jobs_page,
    })

def job_detail(request, id, slug):
    job = get_object_or_404(Job, id=id)
    
    # 1. SEO Canoncial Check
    if job.slug and job.slug != slug:
        return redirect('job_detail', id=job.id, slug=job.slug, permanent=True)

    return render(request, 'jobs/job_detail.html', {'job': job})

def post_job(request):
    if request.method == 'POST':
        form = JobPostForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            if not job.location:
                job.location = "Remote"

            plan = form.cleaned_data.get('plan')
            job.plan_name = plan
            
            job.is_featured = False
            job.is_pinned = False
            job.screening_status = 'pending'
            job.is_active = False 
            job.tags = f"User Submission: {plan}"
            
            job.save() 
            form.save_m2m()

            new_tools_text = form.cleaned_data.get('new_tools')
            if new_tools_text:
                category, _ = Category.objects.get_or_create(name="User Submitted", defaults={'slug': 'user-submitted'})
                tool_names = [t.strip() for t in new_tools_text.split(',') if t.strip()]
                for name in tool_names:
                    tool, created = Tool.objects.get_or_create(
                        name__iexact=name, 
                        defaults={'name': name, 'slug': slugify(name), 'category': category}
                    )
                    job.tools.add(tool)

            cache.delete('popular_tech_stacks')

            if plan == 'featured':
                if not settings.STRIPE_SECRET_KEY:
                     return HttpResponse("CRITICAL ERROR: STRIPE_SECRET_KEY is missing.", status=500)

                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': 'usd',
                            'unit_amount': 9900,
                            'product_data': {
                                'name': 'Featured Job Post',
                                'description': f'Premium listing for {job.title} at {job.company}',
                            },
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    success_url=settings.DOMAIN_URL + f'/post-job/success/?plan=featured&session_id={{CHECKOUT_SESSION_ID}}',
                    cancel_url=settings.DOMAIN_URL + '/post-job/',
                    metadata={'job_id': job.id, 'plan': 'featured'}
                )
                return redirect(checkout_session.url)
            
            return redirect('/post-job/success/?plan=free')
    else:
        form = JobPostForm()
    return render(request, 'jobs/post_job.html', {'form': form})

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except ValueError: return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError: return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        job_id = session.get('metadata', {}).get('job_id')
        
        if job_id:
            try:
                job = Job.objects.get(id=job_id)
                job.is_featured = True
                job.is_pinned = True
                job.screening_status = 'approved'
                job.is_active = True
                job.save()
                cache.delete('popular_tech_stacks')
                send_job_alert(job)
            except Job.DoesNotExist:
                print(f"❌ ERROR: Job {job_id} not found.")

    return HttpResponse(status=200)

def post_job_success(request):
    return render(request, 'jobs/post_job_success.html')

def subscribe(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        if email: 
            subscriber, created = Subscriber.objects.get_or_create(email=email)
            if created:
                send_welcome_email(email)
            return JsonResponse({"success": True})
            
    return JsonResponse({"success": False}, status=400)

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
        job.screening_status = "approved"
        job.is_active = True 
        job.screened_at = timezone.now()
        job.save()
        cache.delete('popular_tech_stacks') 
        send_job_alert(job)
        
    elif action == "reject":
        job.screening_status = "rejected"; job.is_active = False; job.save()
    elif action == "pending":
        job.screening_status = "pending"; job.save()
    return redirect(request.META.get("HTTP_REFERER", "review_queue"))
