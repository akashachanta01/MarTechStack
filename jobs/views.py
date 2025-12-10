from django.shortcuts import render
from .models import Job, Category

def job_list(request):
    # 1. Start with all active jobs
    jobs = Job.objects.filter(is_active=True).order_by('-created_at')
    
    # 2. Check for filters in the URL (e.g., ?category=marketing-automation)
    category_slug = request.GET.get('category')
    if category_slug:
        jobs = jobs.filter(tools__category__slug=category_slug).distinct()

    # 3. Get all categories for the sidebar
    categories = Category.objects.all()

    context = {
        'jobs': jobs,
        'categories': categories,
        'current_category': category_slug,
    }
    return render(request, 'jobs/job_list.html', context)