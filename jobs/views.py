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
from django.contrib import messages 
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives

from .models import Job, Tool, Category, Subscriber 
from .forms import JobPostForm, ContactForm
from .emails import send_job_alert, send_welcome_email, send_admin_new_subscriber_alert

stripe.api_key = settings.STRIPE_SECRET_KEY

# Mapping to consolidate variations of tool names for filtering
TOOL_MAPPING = {
    'salesforce marketing cloud': 'Salesforce', 'sfmc': 'Salesforce', 'pardot': 'Salesforce',
    'marketo': 'Adobe', 'Adobe Experience Platform': 'Adobe', 'aep': 'Adobe',
    'hubspot': 'HubSpot', 'google analytics': 'Google', 'ga4': 'Google',
    'segment': 'Data Stack', 'tealium': 'Data Stack', 'snowflake': 'Data Stack',
    'outreach': 'Sales Tech', 'salesloft': 'Sales Tech', 'braze': 'Automation',
    'shopify': 'Commerce', 'the trade desk': 'AdTech'
}

def job_list(request):
    query = request.GET.get("q", "").strip()
    vendor_query = request.GET.get("vendor", "").strip() 
    location_query = request.GET.get("l", "").strip()
    country_query = request.GET.get("country", "").strip()
    work_arrangement_filter = request.GET.get("arrangement", "").strip().lower()
    role_type_filter = request.GET.get("rtype", "").strip().lower()

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
    
    if country_query:
        jobs = jobs.filter(location__icontains=country_query)

    if work_arrangement_filter:
        jobs = jobs.filter(work_arrangement__iexact=work_arrangement_filter)
    
    if role_type_filter:
        jobs = jobs.filter(role_type__iexact=role_type_filter)

    paginator = Paginator(jobs.distinct(), 25)
    page_number = request.GET.get("page")
    jobs_page = paginator.get_page(page_number)

    return render(request, "jobs/job_list.html", {
        "jobs": jobs_page, 
        "query": query, 
        "location_filter": location_query,
        "selected_country": country_query,
        "vendor_filter": vendor_query,
        "current_arrangement": work_arrangement_filter,
        "current_rtype": role_type_filter,
    })

# --- BLOG VIEW (NEW) ---
def blog_list(request):
    return render(request, 'jobs/blog_list.html')

# --- SEO: LANDING PAGE GENERATOR ---
def seo_landing_page(request, location_slug=None, tool_slug=None):
    tool = None
    if tool_slug:
        clean_tool_slug = tool_slug.replace("-jobs", "")
        tool = get_object_or_404(Tool, slug=clean_tool_slug)

    # EXPANDED LOCATION MAPPING
    SEO_LOCATIONS = {
        "remote": "Remote",
        "new-york": "New York",
        "nyc": "New York",
        "san-francisco": "San Francisco",
        "sf": "San Francisco",
        "london": "London",
        "chicago": "Chicago",
        "austin": "Austin",
        "los-angeles": "Los Angeles",
        "toronto": "Toronto",
        "berlin": "Berlin",
        "singapore": "Singapore",
        "sydney": "Sydney",
        "bengaluru": "Bengaluru",
        "bangalore": "Bengaluru",
        "boston": "Boston",
        "seattle": "Seattle",
        "denver": "Denver",
        "atlanta": "Atlanta",
        "amsterdam": "Amsterdam",
        "dublin": "Dublin"
    }

    location_name = "Remote" # Default
    if location_slug:
        # Check explicit map first, then fallback to title case (e.g. "san-diego" -> "San Diego")
        location_name = SEO_LOCATIONS.get(location_slug.lower(), location_slug.replace("-", " ").title())

    jobs = Job.objects.filter(is_active=True, screening_status='approved')
    
    if tool: 
        jobs = jobs.filter(tools=tool)
    
    if location_name == "Remote": 
        jobs = jobs.filter(work_arrangement="remote")
    else: 
        jobs = jobs.filter(location__icontains=location_name)

    if jobs.count() == 0:
        base_url = "/?q="
        if tool: base_url += tool.name
        if location_name: base_url += f"&l={location_name}"
        return redirect(base_url)

    # Dynamic Headers
    if tool and location_name:
        page_title = f"{location_name} {tool.name} Jobs"
        meta_desc = f"Apply to the best {tool.name} jobs in {location_name}. Curated Marketing Operations roles."
        header_text = f"{location_name} <span class='text-martech-green'>{tool.name}</span> Jobs"
    elif tool:
        page_title = f"{tool.name} Jobs"
        meta_desc = f"Find top {tool.name} roles. Marketing Automation & Ops jobs."
        header_text = f"Top <span class='text-martech-green'>{tool.name}</span> Jobs"
    else:
        page_title = f"Marketing Ops Jobs in {location_name}"
        meta_desc = f"Find the best MarTech and Marketing Operations jobs in {location_name}."
        header_text = f"MarTech Jobs in <span class='text-martech-green'>{location_name}</span>"

    return render(request, 'jobs/tool_detail.html', {
        'tool': tool, 
        'jobs': jobs.order_by('-is_pinned', '-created_at'),
        'custom_title': page_title,
        'custom_header': header_text,
        'custom_desc': meta_desc,
        'is_seo_landing': True
    })

# --- SEO: SALARY GUIDE ---
def salary_guide(request):
    data = cache.get('salary_guide_data')
    
    if not data:
        tools = Tool.objects.annotate(job_count=Count('jobs', filter=Q(jobs__is_active=True))).filter(job_count__gt=2).order_by('-job_count')
        salary_stats = []
        
        for tool in tools:
            jobs = tool.jobs.filter(is_active=True, screening_status='approved')
            min_sum, max_sum, count = 0, 0, 0
            
            for job in jobs:
                s_min, s_max = job.get_salary_min_max()
                if s_min and s_max:
                    min_sum += s_min
                    max_sum += s_max
                    count += 1
            
            if count > 0:
                avg_min = int(min_sum / count)
                avg_max = int(max_sum / count)
                salary_stats.append({
                    'tool': tool,
                    'avg_min': avg_min,
                    'avg_max': avg_max,
                    'count': count
                })
        
        salary_stats.sort(key=lambda x: x['avg_max'], reverse=True)
        data = salary_stats
        cache.set('salary_guide_data', data, 86400) # 24 hrs

    return render(request, 'jobs/salary_guide.html', {'salary_stats': data})

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

def tool_detail(request, slug):
    tool = get_object_or_404(Tool, slug=slug)
    jobs = Job.objects.filter(tools=tool, is_active=True, screening_status='approved').order_by('-is_pinned', '-created_at')
    paginator = Paginator(jobs, 20)
    jobs_page = paginator.get_page(request.GET.get('page'))
    return render(request, 'jobs/tool_detail.html', {'tool': tool, 'jobs': jobs_page})

def job_detail(request, id, slug):
    job = get_object_or_404(Job, id=id, is_active=True, screening_status='approved')
    if job.slug and job.slug != slug: 
        return redirect('job_detail', id=job.id, slug=job.slug, permanent=True)
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
                    # --- REPAIR LOGIC START (Fixes MultipleObjectsReturned) ---
                    target_slug = slugify(name)
                    
                    # 1. Try to find tool by SLUG (Best Match)
                    tool = Tool.objects.filter(slug=target_slug).first()

                    # 2. If not found, try Name Case-Insensitive (Catch "HubSpot" vs "hubspot")
                    if not tool:
                        tool = Tool.objects.filter(name__iexact=name).first()

                    # 3. If still not found, CREATE it safely
                    if not tool:
                        try:
                            tool = Tool.objects.create(name=name, slug=target_slug, category=category)
                        except Exception:
                            # If create fails (race condition or duplicate), fetch whatever exists
                            tool = Tool.objects.filter(name__iexact=name).first()

                    # 4. Add the tool if we found/created one
                    if tool:
                        job.tools.add(tool)
                    # --- REPAIR LOGIC END ---

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
            try: validate_email(email)
            except ValidationError: return JsonResponse({"success": False, "error": "Invalid email format."}, status=400)
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
            job.screening_status = "approved"; job.is_active = True; job.screened_at = timezone.now(); job.save()
            cache.delete('popular_tech_stacks_v2'); cache.delete('available_countries_v2'); send_job_alert(job)
    elif action == "reject": job.screening_status = "rejected"; job.is_active = False; job.save()
    elif action == "pending": job.screening_status = "pending"; job.save()
    return redirect(request.META.get("HTTP_REFERER", "review_queue"))

def about(request): return render(request, 'jobs/about.html')
def for_employers(request): return render(request, 'jobs/for_employers.html')

def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data
            reply_to = [cleaned["email"]]
            recipient = "hello@martechstack.io"
            email = EmailMultiAlternatives(
                subject=f"Contact form: {cleaned['subject']}",
                body=cleaned["message"],
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient],
                reply_to=reply_to
            )
            try:
                email.send(fail_silently=False)
                messages.success(request, "Thanks for reaching out! We'll get back to you soon.")
                return redirect("contact")
            except Exception:
                messages.error(request, "We couldn't send your message right now. Please try again.")
    else:
        form = ContactForm()
    return render(request, "jobs/contact.html", {"form": form})
