import stripe
import json
import os
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, Value, IntegerField, Count, Max
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.cache import cache
from django.utils.text import slugify
from django.http import HttpResponse, JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages 
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives

from .models import Job, Tool, Category, Subscriber, BlogPost
from .forms import JobPostForm, ContactForm
from .emails import send_job_alert, send_welcome_email, send_admin_new_subscriber_alert

stripe.api_key = settings.STRIPE_SECRET_KEY


def _client_ip(request):
    # Render puts the real client IP first in X-Forwarded-For.
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _rate_limited(request, action, limit=5, window_seconds=3600):
    """Returns True if this IP exceeded `limit` requests for `action` within the window."""
    key = f"ratelimit:{action}:{_client_ip(request)}"
    count = cache.get_or_set(key, 0, timeout=window_seconds)
    if count >= limit:
        return True
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window_seconds)
    return False

TOOL_MAPPING = {
    'salesforce marketing cloud': 'Salesforce', 'sfmc': 'Salesforce', 'pardot': 'Salesforce',
    'marketo': 'Adobe', 'Adobe Experience Platform': 'Adobe', 'aep': 'Adobe',
    'hubspot': 'HubSpot', 'google analytics': 'Google', 'ga4': 'Google',
    'segment': 'Data Stack', 'tealium': 'Data Stack', 'snowflake': 'Data Stack',
    'outreach': 'Sales Tech', 'salesloft': 'Sales Tech', 'braze': 'Automation',
    'shopify': 'Commerce', 'the trade desk': 'AdTech'
}

# --- SEO CROSS-LINKING DATA ---
SEO_CROSS_CITIES = ["New York", "San Francisco", "Austin", "Chicago", "Seattle", "Boston", "Los Angeles", "Denver", "Atlanta", "London"]
SEO_CROSS_STATES = ["California", "Texas", "New York", "Florida", "Illinois", "Pennsylvania", "Washington", "Colorado"]

def job_list(request):
    query = request.GET.get("q", "").strip()
    vendor_query = request.GET.get("vendor", "").strip()
    location_query = request.GET.get("l", "").strip()
    country_query = request.GET.get("country", "").strip()
    work_arrangement_filter = request.GET.get("arrangement", "").strip().lower()
    role_type_filter = request.GET.get("rtype", "").strip().lower()
    tool_filter = request.GET.get("tool", "").strip()
    sort = request.GET.get("sort", "").strip().lower()

    jobs = Job.objects.filter(is_active=True, screening_status="approved").prefetch_related("tools")

    if tool_filter:
        jobs = jobs.filter(tools__slug=tool_filter)

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
    
    if sort == "oldest":
        jobs = jobs.order_by('created_at')
    elif query:
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

    # On the unfiltered homepage, show only the latest 10 roles with a
    # "View all jobs" link. Active searches/filters (or ?all=1) get the full
    # paginated list.
    has_filters = bool(
        query or vendor_query or location_query or country_query
        or work_arrangement_filter or role_type_filter or tool_filter or sort
    )
    show_all = request.GET.get("all") == "1"
    limited = not has_filters and not show_all

    distinct_jobs = jobs.distinct()
    total_count = distinct_jobs.count()

    if limited:
        paginator = Paginator(distinct_jobs, 10)
        jobs_page = paginator.get_page(1)
    else:
        paginator = Paginator(distinct_jobs, 25)
        page_number = request.GET.get("page")
        jobs_page = paginator.get_page(page_number)

    # Querystring with all current filters except page, so pagination links keep them.
    params = request.GET.copy()
    params.pop("page", None)
    filter_qs = params.urlencode()

    return render(request, "jobs/job_list.html", {
        "jobs": jobs_page,
        "query": query,
        "location_filter": location_query,
        "selected_country": country_query,
        "vendor_filter": vendor_query,
        "current_arrangement": work_arrangement_filter,
        "current_rtype": role_type_filter,
        "selected_tool": tool_filter,
        "current_sort": sort,
        "filter_qs": filter_qs,
        "limited": limited,
        "total_count": total_count,
    })

# --- CATEGORY LANDING PAGES (Engineering / Operations / Data) ---
CATEGORY_CONFIG = {
    "engineering": {
        "name": "Engineering",
        "eyebrow": "Build the systems",
        "description": "Marketing-engineering, CDP, integrations, and growth-engineering roles — the people who build and own the systems behind the funnel.",
        "placeholder": "Search engineering jobs…",
        "keywords": ["engineer", "developer", "architect", "technologist", "integration",
                     "engineering", "implementation", "devops", "platform"],
        "tool_slugs": ["segment", "dbt", "snowflake", "ga4", "mparticle", "customer-io",
                       "rudderstack", "amplitude", "bigquery"],
    },
    "operations": {
        "name": "Operations",
        "eyebrow": "Run the stack",
        "description": "Marketing Ops, RevOps, lifecycle, and campaign operations — the people who run the platforms and orchestrate the funnel.",
        "placeholder": "Search operations jobs…",
        "keywords": ["operations", "ops", "admin", "administrator", "lifecycle", "campaign",
                     "marketing automation", "revops", "demand gen", "demand generation",
                     "crm manager", "manager, marketing"],
        "tool_slugs": ["hubspot", "marketo", "salesforce", "braze", "klaviyo", "pardot",
                       "iterable", "marketing-cloud", "eloqua"],
    },
    "data": {
        "name": "Data",
        "eyebrow": "Turn data into growth",
        "description": "Analytics engineering, BI, and data roles — the people who turn marketing data into insight and measurable growth.",
        "placeholder": "Search data jobs…",
        "keywords": ["data", "analytics", "analyst", "insight", "reporting", "intelligence",
                     "measurement", "attribution", "business intelligence"],
        "tool_slugs": ["snowflake", "segment", "ga4", "amplitude", "looker", "bigquery",
                       "tableau", "mixpanel", "dbt"],
    },
}

def category_detail(request, slug):
    config = CATEGORY_CONFIG.get(slug)
    if not config:
        raise Http404("Unknown category")

    query = request.GET.get("q", "").strip()
    location_query = request.GET.get("l", "").strip()
    tool_filter = request.GET.get("tool", "").strip()
    work_arrangement_filter = request.GET.get("arrangement", "").strip().lower()

    jobs = Job.objects.filter(is_active=True, screening_status="approved").prefetch_related("tools")

    # Scope to the category: title keyword match OR carries a category tool.
    cat_q = Q()
    for kw in config["keywords"]:
        cat_q |= Q(title__icontains=kw)
    cat_q |= Q(tools__slug__in=config["tool_slugs"])
    jobs = jobs.filter(cat_q)

    # Optional user refinements within the category.
    if query:
        jobs = jobs.filter(
            Q(title__icontains=query) | Q(company__icontains=query) | Q(tools__name__icontains=query)
        )
    if tool_filter:
        jobs = jobs.filter(tools__slug=tool_filter)
    if location_query:
        jobs = jobs.filter(location__icontains=location_query)
    if work_arrangement_filter:
        jobs = jobs.filter(work_arrangement__iexact=work_arrangement_filter)

    jobs = jobs.order_by("-is_pinned", "-created_at").distinct()
    total_count = jobs.count()

    paginator = Paginator(jobs, 25)
    jobs_page = paginator.get_page(request.GET.get("page"))

    # Top tech stacks within this category (only those that have live jobs).
    top_stacks = (
        Tool.objects.filter(slug__in=config["tool_slugs"])
        .annotate(job_count=Count("jobs", filter=Q(jobs__is_active=True, jobs__screening_status="approved")))
        .filter(job_count__gt=0)
        .order_by("-job_count")[:6]
    )

    # Tool options for the in-page filter dropdown.
    category_tools = Tool.objects.filter(slug__in=config["tool_slugs"]).order_by("name")

    params = request.GET.copy()
    params.pop("page", None)
    filter_qs = params.urlencode()

    return render(request, "jobs/category.html", {
        "category": config,
        "category_slug": slug,
        "jobs": jobs_page,
        "total_count": total_count,
        "query": query,
        "location_filter": location_query,
        "selected_tool": tool_filter,
        "current_arrangement": work_arrangement_filter,
        "top_stacks": top_stacks,
        "category_tools": category_tools,
        "filter_qs": filter_qs,
    })

def all_jobs(request):
    """Dedicated browse-all-jobs board (the 'Jobs' nav destination)."""
    query = request.GET.get("q", "").strip()
    location_query = request.GET.get("l", "").strip()
    tool_filter = request.GET.get("tool", "").strip()
    work_arrangement_filter = request.GET.get("arrangement", "").strip().lower()
    function = request.GET.get("function", "").strip().lower()
    sort = request.GET.get("sort", "").strip().lower()

    jobs = Job.objects.filter(is_active=True, screening_status="approved").prefetch_related("tools")

    # Optional function scope (Engineering / Operations / Data).
    if function in CATEGORY_CONFIG:
        config = CATEGORY_CONFIG[function]
        cat_q = Q()
        for kw in config["keywords"]:
            cat_q |= Q(title__icontains=kw)
        cat_q |= Q(tools__slug__in=config["tool_slugs"])
        jobs = jobs.filter(cat_q)

    if query:
        jobs = jobs.filter(
            Q(title__icontains=query) | Q(company__icontains=query) | Q(tools__name__icontains=query)
        )
    if tool_filter:
        jobs = jobs.filter(tools__slug=tool_filter)
    if location_query:
        jobs = jobs.filter(location__icontains=location_query)
    if work_arrangement_filter:
        jobs = jobs.filter(work_arrangement__iexact=work_arrangement_filter)

    if sort == "oldest":
        jobs = jobs.order_by("created_at")
    else:
        jobs = jobs.order_by("-is_pinned", "-created_at")

    jobs = jobs.distinct()
    total_count = jobs.count()

    paginator = Paginator(jobs, 25)
    jobs_page = paginator.get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)
    filter_qs = params.urlencode()

    return render(request, "jobs/all_jobs.html", {
        "jobs": jobs_page,
        "total_count": total_count,
        "query": query,
        "location_filter": location_query,
        "selected_tool": tool_filter,
        "current_arrangement": work_arrangement_filter,
        "current_function": function,
        "current_sort": sort,
        "view_mode": request.GET.get("view", "list"),
        "filter_qs": filter_qs,
    })

def blog_list(request):
    search_query = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '').strip()

    posts = BlogPost.objects.filter(is_published=True).order_by('-published_at')

    if search_query:
        posts = posts.filter(
            Q(title__icontains=search_query) | 
            Q(content__icontains=search_query) |
            Q(excerpt__icontains=search_query)
        )
    
    if category_filter:
        posts = posts.filter(category__iexact=category_filter)

    featured_post = None
    remaining_posts = posts

    if not search_query and not category_filter and posts.exists():
        featured_post = posts.first()
        remaining_posts = posts[1:]
    
    return render(request, 'jobs/blog_list.html', {
        'featured_post': featured_post,
        'posts': remaining_posts,
        'search_query': search_query,
        'current_category': category_filter
    })

def post_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug, is_published=True)
    related_posts = BlogPost.objects.filter(is_published=True).exclude(id=post.id).order_by('-published_at')[:2]
    sidebar_jobs = Job.objects.filter(is_active=True, screening_status='approved').order_by('-is_featured', '-created_at')[:2]
    
    return render(request, 'jobs/post_detail.html', {
        'post': post,
        'related_posts': related_posts,
        'sidebar_jobs': sidebar_jobs,
    })

# --- SEO: LANDING PAGE GENERATOR ---
def seo_landing_page(request, location_slug=None, tool_slug=None):
    tool = None
    if tool_slug:
        clean_tool_slug = tool_slug.replace("-jobs", "")
        tool = get_object_or_404(Tool, slug=clean_tool_slug)

    SEO_LOCATIONS = {
        "nyc": "New York", "sf": "San Francisco", "la": "Los Angeles", "dfw": "Dallas",
        "united-states": "United States"
    }

    location_name = "Remote" 
    if location_slug:
        location_name = SEO_LOCATIONS.get(location_slug.lower(), location_slug.replace("-", " ").title())

    jobs = Job.objects.filter(is_active=True, screening_status='approved')
    if tool: jobs = jobs.filter(tools=tool)
    if location_name == "Remote": jobs = jobs.filter(work_arrangement="remote")
    elif location_name != "United States": jobs = jobs.filter(location__icontains=location_name)

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

    paginator = Paginator(jobs.order_by('-is_pinned', '-created_at'), 20)
    jobs_page = paginator.get_page(request.GET.get('page'))

    return render(request, 'jobs/tool_detail.html', {
        'tool': tool, 'jobs': jobs_page,
        'custom_title': page_title, 'custom_header': header_text, 'custom_desc': meta_desc, 
        'is_seo_landing': True, 'location_name': location_name,
        'cross_cities': SEO_CROSS_CITIES, 'cross_states': SEO_CROSS_STATES
    })

def salary_guide(request):
    data = cache.get('salary_guide_data_v2')
    if not data:
        tools = Tool.objects.annotate(
            job_count=Count('jobs', filter=Q(jobs__is_active=True))
        ).filter(job_count__gt=0).order_by('-job_count')
        
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
                salary_stats.append({
                    'tool': tool, 
                    'avg_min': int(min_sum / count), 
                    'avg_max': int(max_sum / count), 
                    'count': count
                })
                
        salary_stats.sort(key=lambda x: x['avg_max'], reverse=True)
        data = salary_stats
        cache.set('salary_guide_data_v2', data, 3600)
        
    return render(request, 'jobs/salary_guide.html', {'salary_stats': data})

def unsubscribe(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        if email:
            deleted_count, _ = Subscriber.objects.filter(email=email).delete()
            if deleted_count > 0: messages.success(request, f"✅ {email} has been unsubscribed.")
            else: messages.warning(request, "⚠️ That email was not found in our list.")
    return render(request, "jobs/unsubscribe.html")

def tool_detail(request, slug):
    tool = get_object_or_404(Tool, slug=slug)
    jobs = Job.objects.filter(tools=tool, is_active=True, screening_status='approved').order_by('-is_pinned', '-created_at')
    paginator = Paginator(jobs, 20)
    jobs_page = paginator.get_page(request.GET.get('page'))
    return render(request, 'jobs/tool_detail.html', {
        'tool': tool, 'jobs': jobs_page, 'location_name': 'Global/Remote',
        'cross_cities': SEO_CROSS_CITIES, 'cross_states': SEO_CROSS_STATES
    })

def job_detail(request, id, slug):
    job = get_object_or_404(Job, id=id, is_active=True, screening_status='approved')
    if job.slug and job.slug != slug: return redirect('job_detail', id=job.id, slug=job.slug, permanent=True)
    return render(request, 'jobs/job_detail.html', {'job': job})

def post_job(request):
    if request.method == 'POST':
        if _rate_limited(request, 'post_job', limit=5, window_seconds=3600):
            return HttpResponse("Too many submissions. Please try again later.", status=429)
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
                    target_slug = slugify(name)
                    tool = Tool.objects.filter(slug=target_slug).first()
                    if not tool: tool = Tool.objects.filter(name__iexact=name).first()
                    if not tool:
                        try: tool = Tool.objects.create(name=name, slug=target_slug, category=category)
                        except: tool = Tool.objects.filter(name__iexact=name).first()
                    if tool: job.tools.add(tool)

            cache.delete('popular_tech_stacks_v3'); cache.delete('available_countries_v2')
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
    # Refuse to process webhooks at all if signature verification isn't configured.
    if not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse(status=500)
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        job_id = session.get('metadata', {}).get('job_id')
        # Only publish the job if Stripe confirms the money actually arrived.
        if job_id and session.get('payment_status') == 'paid':
            try: 
                job = Job.objects.get(id=job_id); job.is_featured = True; job.is_pinned = True; job.screening_status = 'approved'; job.is_active = True; job.save()
                cache.delete('popular_tech_stacks_v3'); cache.delete('available_countries_v2'); send_job_alert(job)
            except Job.DoesNotExist: pass
    return HttpResponse(status=200)

def post_job_success(request): return render(request, 'jobs/post_job_success.html')

def subscribe(request):
    if request.method == "POST":
        if _rate_limited(request, 'subscribe', limit=5, window_seconds=3600):
            return JsonResponse({"success": False, "error": "Too many attempts. Try again later."}, status=429)
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
            cache.delete('popular_tech_stacks_v3'); cache.delete('available_countries_v2'); send_job_alert(job)
    elif action == "reject": job.screening_status = "rejected"; job.is_active = False; job.save()
    elif action == "pending": job.screening_status = "pending"; job.save()
    return redirect(request.META.get("HTTP_REFERER", "review_queue"))

def about(request): return render(request, 'jobs/about.html')
def for_employers(request): return render(request, 'jobs/for_employers.html')

def contact(request):
    if request.method == "POST":
        if _rate_limited(request, 'contact', limit=5, window_seconds=3600):
            messages.error(request, "Too many messages. Please try again later.")
            return redirect("contact")
        form = ContactForm(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data
            reply_to = [cleaned["email"]]
            recipient = "martechjobs@gmail.com"
            email = EmailMultiAlternatives(subject=f"Contact form: {cleaned['subject']}", body=cleaned["message"], from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient], reply_to=reply_to)
            try: email.send(fail_silently=False); messages.success(request, "Thanks for reaching out! We'll get back to you soon."); return redirect("contact")
            except: messages.error(request, "We couldn't send your message right now. Please try again.")
    else: form = ContactForm()
    return render(request, "jobs/contact.html", {"form": form})

def company_list(request):
    companies = Job.objects.filter(is_active=True, screening_status='approved')\
        .values('company', 'company_logo')\
        .annotate(job_count=Count('id'), last_posted=Max('created_at'))\
        .order_by('-last_posted')
    
    return render(request, 'jobs/company_list.html', {'companies': companies})

def company_detail(request, company_slug):
    company_name = company_slug.replace('-', ' ')
    
    jobs = Job.objects.filter(
        company__iexact=company_name, 
        is_active=True, 
        screening_status='approved'
    ).order_by('-created_at')

    if not jobs:
        return redirect('job_list')

    canonical_job = jobs.first()
    
    return render(request, 'jobs/company_detail.html', {
        'company_name': canonical_job.company,
        'company_logo': canonical_job.company_logo,
        'jobs': jobs,
        'tech_stack': Tool.objects.filter(jobs__in=jobs).distinct()[:5]
    })

def directory(request):
    tools = Tool.objects.all().annotate(job_count=Count('jobs', filter=Q(jobs__is_active=True))).order_by('-job_count')
    
    # 50 States Matrix for Programmatic SEO
    states = [
        "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", 
        "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", 
        "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", 
        "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", 
        "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", 
        "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", 
        "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", 
        "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia", 
        "Washington", "West Virginia", "Wisconsin", "Wyoming"
    ]
    
    # Top Metro Areas Matrix for Programmatic SEO
    top_cities = [
        "New York", "San Francisco", "Austin", "Chicago", "Seattle", "Boston", 
        "Los Angeles", "Denver", "Atlanta", "Dallas", "Miami", "Toronto", "London"
    ]
    
    return render(request, 'jobs/directory.html', {
        'tools': tools,
        'states': states,
        'top_cities': top_cities,
        'seo_title': "MarTech Jobs Directory - Browse by Tech Stack & Location"
    })
