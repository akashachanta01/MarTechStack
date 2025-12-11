from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Job, Category

def job_list(request):
    # 1. Start with all active jobs
    jobs = Job.objects.filter(is_active=True).order_by('-created_at')
    
    # 2. Search Logic
    query = request.GET.get('q')
    location = request.GET.get('loc')
    is_remote = request.GET.get('remote')
    category_slug = request.GET.get('category')

    if query:
        # Search everywhere safely
        jobs = jobs.filter(
            Q(title__icontains=query) | 
            Q(company__icontains=query) | 
            Q(description__icontains=query) |
            Q(tags__icontains=query) |
            Q(tools__name__icontains=query)
        ).distinct()

    if location:
        jobs = jobs.filter(location__icontains=location)

    if is_remote:
        jobs = jobs.filter(location__icontains='Remote')

    if category_slug:
        jobs = jobs.filter(tools__category__slug=category_slug).distinct()

    # 3. Sidebar data
    categories = Category.objects.all()

    context = {
        'jobs': jobs,
        'categories': categories,
        'current_category': category_slug,
        'search_query': query,
        'search_loc': location,
        'is_remote': is_remote,
    }
    return render(request, 'jobs/job_list.html', context)

def job_detail(request, pk):
    job = get_object_or_404(Job, pk=pk)
    return render(request, 'jobs/job_detail.html', {'job': job})
