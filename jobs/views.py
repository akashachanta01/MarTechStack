import stripe
import json
import os
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, Value, IntegerField, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.cache import cache
from django.utils.text import slugify
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages # <--- Added this

from .models import Job, Tool, Category, Subscriber 
from .forms import JobPostForm
from .emails import send_job_alert, send_welcome_email, send_admin_new_subscriber_alert

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

    # --- TOPIC CLUSTERS ---
    popular_tech_stacks = cache.get('popular_tech_stacks_v2')
    if popular_tech_stacks is None:
        popular_tech_stacks = Tool.objects.filter(
            jobs__is_active=True, 
            jobs__screening_status='approved'
        ).values('name', 'slug').annotate(count=Count('jobs')).order_by('-count')[:10]
        cache.set('popular_tech_stacks_v2', list(popular_tech_stacks), 3600)

    # --- DYNAMIC COUNTRY LIST (STRICT FILTER) ---
    available_countries = cache.get('available_countries_v2')
    if available_countries is None:
        raw_locs = Job.objects.filter(is_active=True).values_list('location', flat=True).distinct()
        country_set = set()
        blocklist = ["not specified", "on-site", "latin america", "va de los poblados"]
        for loc in raw_locs:
            if not loc: continue
            if any(r in loc.lower() for r in ['remote', 'anywhere', 'wfh']): continue
            if any(b in loc.lower() for b in blocklist): continue
            parts = loc.split(',')
            if len(parts) >= 1:
                country = parts[-1].strip()
                if len(country) > 3 and not any(char.isdigit() for char in country): 
                    country_set.add(country)
        available_countries = sorted(list(country_set))
        cache.set('available_countries_v2', available_countries, 3600)

    return render(request, "jobs/job_list.html", {
        "jobs": jobs_page, "query": query, "location_filter": location_query,
        "popular_tech_stacks": popular_tech_stacks, "vendor_filter": vendor_query,
        "available_countries": available_countries,
    })

# --- NEW UNSUBSCRIBE VIEW ---
def unsubscribe(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        if email:
            deleted_count, _ = Subscriber.objects.filter(email=email).delete()
            if deleted_count > 0:
                messages.success(request, f"✅ {email} has been unsubscribed.")
            else:
                messages.warning(request, "⚠️ That email was not found in our list.")
    return render(request, "jobs/unsubscribe.html")

# --- OTHER VIEWS ---
def tool_detail(request, slug):
    tool = get_object_or_404(Tool, slug=slug)
    jobs = Job.objects.filter(tools=tool, is_active=True, screening_status='approved').order_by('-is_pinned', '-created_at')
    paginator = Paginator(jobs, 20)
    jobs_page = paginator.get_page(request.GET.get('page'))
    return render(request, 'jobs/tool_detail.html', {'tool': tool, 'jobs': jobs_page})

def job_detail(request, id, slug):
    job = get_object_or_404(Job, id=id)
    if job.slug and job.slug != slug: return redirect('job_detail', id=job.id, slug=job.slug, permanent=True)
    return render(request, 'jobs/job_detail.html', {'job': job})

def post_job(request):
    if request.method == 'POST':
        form = JobPostForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            if not job.location: job.location = "Remote"
            plan = form.cleaned_data.get('plan')
            job.plan_name = plan
            job.is_featured = False; job.is_pinned = False; job.screening_status = 'pending'; job.is_active = False 
            job.tags = f"User Submission: {plan}"; job.save(); form.save_m2m()
            new_tools_text = form.cleaned_data.get('new_tools')
            if new_tools_text:
                category, _ = Category.objects.get_or_create(name="User Submitted", defaults={'slug': 'user-submitted'})
                for name in [t.strip() for t in new_tools_text.split(',') if t.strip()]:
                    tool, _ = Tool.objects.get_or_create(name__iexact=name, defaults={'name': name, 'slug': slugify(name), 'category': category})
                    job.tools.add(tool)
            cache.delete('popular_tech_stacks_v2'); cache.delete('available_countries_v2')
            if plan == 'featured':
                if not settings.STRIPE_SECRET_KEY: return HttpResponse("Error: STRIPE_SECRET_KEY missing", status=500)
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{'price_data': {'currency': 'usd', 'unit_amount': 9900, 'product_data': {'name': 'Featured Job Post', 'description': f'Premium listing for {job.title}'}}, 'quantity': 1}],
                    mode='payment', success_url=settings.DOMAIN_URL + f'/post-job/success/?plan=featured&session_id={{CHECKOUT_SESSION_ID}}', cancel_url=settings.DOMAIN_URL + '/post-job/', metadata={'job_id': job.id, 'plan': 'featured'}
                )
                return redirect(checkout_session.url)
            return redirect('/post-job/success/?plan=free')
    else: form = JobPostForm()
    return render(request, 'jobs/post_job.html', {'form': form})

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    try: event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except: return HttpResponse(status=400)
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        job_id = session.get('metadata', {}).get('job_id')
        if job_id:
            try: 
                job = Job.objects.get(id=job_id); job.is_featured = True; job.is_pinned = True; job.screening_status = 'approved'; job.is_active = True; job.save()
                cache.delete('popular_tech_stacks_v2'); cache.delete('available_countries_v2'); send_job_alert(job)
            except Job.DoesNotExist: pass
    return HttpResponse(status=200)

def post_job_success(request): return render(request, 'jobs/post_job_success.html')

def subscribe(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        if email: 
            sub, created = Subscriber.objects.get_or_create(email=email)
            if created: 
                send_welcome_email(email)
                user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for: ip = x_forwarded_for.split(',')[0]
                else: ip = request.META.get('REMOTE_ADDR')
                send_admin_new_subscriber_alert(email, user_agent, ip)
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
    jobs_page = paginator.get_page(request.GET.get("page"))
    return render(request, "jobs/review_queue.html", {"jobs": jobs_page, "status": status, "q": q})

@staff_member_required
def review_action(request, job_id, action):
    job = get_object_or_404(Job, id=job_id)
    if action == "approve": 
        if job.screening_status != "approved":
            job.screening_status = "approved"
            job.is_active = True
            job.screened_at = timezone.now()
            job.save()
            cache.delete('popular_tech_stacks_v2')
            cache.delete('available_countries_v2')
            send_job_alert(job)
    elif action == "reject": job.screening_status = "rejected"; job.is_active = False; job.save()
    elif action == "pending": job.screening_status = "pending"; job.save()
    return redirect(request.META.get("HTTP_REFERER", "review_queue"))
