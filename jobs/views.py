from django.shortcuts import render, get_object_or_404
from .models import Job, Category

def job_list(request):
    jobs = Job.objects.filter(is_active=True).order_by('-created_at')
    
    # Filter by Category (Tech Stack)
    category_slug = request.GET.get('category')
    if category_slug:
        jobs = jobs.filter(tools__category__slug=category_slug).distinct()

    categories = Category.objects.all()

    context = {
        'jobs': jobs,
        'categories': categories,
        'current_category': category_slug,
    }
    return render(request, 'jobs/job_list.html', context)

def job_detail(request, pk):
    job = get_object_or_404(Job, pk=pk)
    return render(request, 'jobs/job_detail.html', {'job': job})
