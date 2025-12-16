from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Job, Tool, Category, Subscriber 

def job_list(request):
    query = request.GET.get("q", "").strip()
    location_query = request.GET.get("l", "").strip()
    tool_filter = request.GET.get("tool", "").strip()
    category_filter = request.GET.get("category", "").strip()
    role_type_filter = request.GET.get("role_type", "").strip()
    remote_filter = request.GET.get("remote", "").strip()

    jobs = (
        Job.objects.filter(is_active=True, screening_status="approved")
        .prefetch_related("tools", "tools__category")
        .order_by("-created_at")
    )

    # 1. Keyword Search
    if query:
        jobs = jobs.filter(
            Q(title__icontains=query)
            | Q(company__icontains=query)
            | Q(description__icontains=query)
            | Q(tools__name__icontains=query)
        ).distinct()

    # 2. Location Search
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

    paginator = Paginator(jobs.distinct(), 25)
    page_number = request.GET.get("page")
    jobs_page = paginator.get_page(page_number)

    tools = Tool.objects.all().select_related("category").order_by("category__name", "name")
    categories = Category.objects.all().order_by("name") 

    context = {
        "jobs": jobs_page,
        "query": query,
        "location_filter": location_query,
        "tool_filter": tool_filter,
        "category_filter": category_filter,
        "role_type_filter": role_type_filter,
        "remote_filter": remote_filter,
        "tools": tools,
        "categories": categories,
    }
    return render(request, "jobs/job_list.html", context)

# ... (rest of your views: job_detail, post_job, etc. remain unchanged) ...
def job_detail(request, job_id):
    job = get_object_or_404(Job, id=job_id, is_active=True, screening_status="approved")
    return render(request, "jobs/job_detail.html", {"job": job})

def post_job(request):
    return render(request, "jobs/post_job.html")

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

    return render(
        request,
        "jobs/review_queue.html",
        {
            "jobs": jobs_page,
            "status": status,
            "q": q,
        },
    )

@staff_member_required
def review_action(request, job_id, action):
    job = get_object_or_404(Job, id=job_id)

    if action == "approve":
        job.screening_status = "approved"
        job.is_active = True
        job.screened_at = job.screened_at or timezone.now()
        job.save(update_fields=["screening_status", "is_active", "screened_at"])
    elif action == "reject":
        job.screening_status = "rejected"
        job.is_active = False
        job.screened_at = job.screened_at or timezone.now()
        job.save(update_fields=["screening_status", "is_active", "screened_at"])
    elif action == "pending":
        job.screening_status = "pending"
        job.save(update_fields=["screening_status"])

    return redirect(request.META.get("HTTP_REFERER", "review_queue"))
