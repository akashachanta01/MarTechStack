from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .models import Job, Category
from .forms import JobSubmissionForm, SubscriberForm

def job_list(request):
    jobs = Job.objects.filter(is_active=True).order_by('-created_at')
    
    # 1. Capture Inputs
    query = request.GET.get('q', '')
    location = request.GET.get('loc', '')
    is_remote = request.GET.get('remote')
    
    # 2. Capture Multiple Checkboxes (This is the new part!)
    selected_categories = request.GET.getlist('category')

    # 3. Filter Logic
    if query:
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

    # Filter by multiple categories if selected
    if selected_categories:
        jobs = jobs.filter(tools__category__slug__in=selected_categories).distinct()

    categories = Category.objects.all()

    context = {
        'jobs': jobs,
        'categories': categories,
        'selected_categories': selected_categories, # Pass back to keep boxes checked
        'search_query': query,
        'search_loc': location,
        'is_remote': is_remote,
    }
    return render(request, 'jobs/job_list.html', context)

def job_detail(request, pk):
    job = get_object_or_404(Job, pk=pk)
    return render(request, 'jobs/job_detail.html', {'job': job})

def post_job(request):
    if request.method == 'POST':
        form = JobSubmissionForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.is_active = False 
            job.save()
            messages.success(request, "🎉 Job submitted! We will review and publish it shortly.")
            return redirect('job_list')
    else:
        form = JobSubmissionForm()
    
    return render(request, 'jobs/post_job.html', {'form': form})

def subscribe(request):
    if request.method == 'POST':
        form = SubscriberForm(request.POST)
        if form.is_valid():
            subscriber = form.save()
            
            # --- SEND WELCOME EMAIL ---
            try:
                send_mail(
                    subject="Welcome to MarTechStack!",
                    message="Thanks for subscribing! You'll get the best MarTech jobs every week.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[subscriber.email],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"❌ Error sending email: {e}")

            messages.success(request, "✅ You're on the list! Watch your inbox.")
        else:
            messages.error(request, "This email is already subscribed or invalid.")
    return redirect('job_list')
