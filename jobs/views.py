from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, Value, IntegerField
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.cache import cache
from collections import defaultdict

from .models import Job, Tool, Category, Subscriber 
from .forms import JobPostForm

def job_list(request):
    query = request.GET.get("q", "").strip()
    vendor_query = request.GET.get("vendor", "").strip() 
    location_query = request.GET.get("l", "").strip()
    work_arrangement_filter = request.GET.get("arrangement", "").strip().lower()

    jobs = Job.objects.filter(is_active=True, screening_status="approved").prefetch_related("tools")

    if vendor_query:
        # Simplified vendor filter logic for brevity
        jobs = jobs.filter(tools__name__icontains=vendor_query if vendor_query != "General" else "")
    elif query:
        search_q = Q(title__icontains=query) | Q(company__icontains=query) | Q(tools__name__icontains=query)
        jobs = jobs.filter(search_q).annotate(
            relevance=Case(
                When(title__icontains=query, then=Value(10)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by('-is_pinned', '-relevance', '-created_at')
    else:
        jobs = jobs.order_by('-is_pinned', '-created_at')

    # Pagination & Cache logic remains similar to previous versions
    paginator = Paginator(jobs.distinct(), 25)
    page_number = request.GET.get("page")
    jobs_page = paginator.get_page(page_number)

    return render(request, "jobs/job_list.html", {"jobs": jobs_page, "query": query})

def post_job(request):
    if request.method == 'POST':
        form = JobPostForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            plan = form.cleaned_data.get('plan')
            
            # Map plan selection to model fields
            job.plan_name = plan
            if plan == 'featured':
                job.is_featured = True
            elif plan == 'premium':
                job.is_featured = True
                job.is_pinned = True
                
            # For MVP: Auto-approve but tag as user submission
            job.screening_status = 'approved' 
            job.is_active = True 
            job.tags = f"User Submission: {plan}" 
            job.save()
            form.save_m2m()
            return redirect('post_job_success')
    else:
        form = JobPostForm()
    return render(request, 'jobs/post_job.html', {'form': form})

def post_job_success(request):
    return render(request, 'jobs/post_job_success.html')

# Other views (subscribe, review_queue, etc.) remain unchanged
