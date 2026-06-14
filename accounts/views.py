import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

from jobs.models import Job, Tool
from .models import UserProfile


@login_required
def dashboard(request):
    profile = request.user.userprofile

    # Evaluate the saved-jobs relation once; derive both the count and the
    # preview slice from the same result instead of re-querying.
    saved_active = list(
        profile.saved_jobs.filter(is_active=True).order_by('-created_at')
    )
    saved_count = len(saved_active)
    saved_preview = saved_active[:5]

    # Evaluate the preferred stack once too.
    stack_tools = list(profile.preferred_stack.all())
    has_stack = bool(stack_tools)

    # Top matches: active jobs using the user's preferred tools.
    if has_stack:
        top_matches = list(
            Job.objects.filter(is_active=True, tools__in=stack_tools)
            .distinct()
            .order_by('-created_at')[:6]
        )
    else:
        top_matches = list(
            Job.objects.filter(is_active=True).order_by('-created_at')[:6]
        )

    checklist = [
        {'label': 'Add your first name', 'done': bool(request.user.first_name), 'url': '/accounts/profile/'},
        {'label': 'Pick your tech stack', 'done': has_stack, 'url': '/accounts/profile/'},
        {'label': 'Set preferred location', 'done': bool(profile.preferred_location), 'url': '/accounts/profile/'},
        {'label': 'Save your first job', 'done': saved_count > 0, 'url': '/jobs/'},
    ]

    ctx = {
        'profile': profile,
        'saved_jobs': saved_preview,
        'top_matches': top_matches,
        'matches_count': len(top_matches),
        'has_stack': has_stack,
        'checklist': checklist,
        'saved_count': saved_count,
        'profile_pct': profile.profile_complete_pct(),
    }
    return render(request, 'accounts/dashboard.html', ctx)


@login_required
def saved_jobs(request):
    profile = request.user.userprofile
    jobs = profile.saved_jobs.filter(is_active=True).order_by('-created_at')
    return render(request, 'accounts/saved_jobs.html', {'saved_jobs': jobs})


@login_required
def profile_edit(request):
    profile = request.user.userprofile
    all_tools = Tool.objects.order_by('name')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        bio = request.POST.get('bio', '').strip()
        preferred_location = request.POST.get('preferred_location', '').strip()
        linkedin_url = request.POST.get('linkedin_url', '').strip()
        tool_ids = request.POST.getlist('preferred_stack')

        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.save()

        profile.bio = bio[:500]
        profile.preferred_location = preferred_location[:100]
        # Normalise and validate the LinkedIn URL: force https, reject any
        # non-http(s) scheme (e.g. javascript:, ftp:) and anything that isn't
        # a real URL. URLField validators don't run on .save(), so do it here.
        if linkedin_url:
            if linkedin_url.startswith('http://'):
                linkedin_url = 'https://' + linkedin_url[len('http://'):]
            elif not linkedin_url.startswith('https://'):
                linkedin_url = 'https://' + linkedin_url
            try:
                URLValidator(schemes=['https'])(linkedin_url)
            except ValidationError:
                linkedin_url = ''
        profile.linkedin_url = linkedin_url
        profile.preferred_stack.set(Tool.objects.filter(id__in=tool_ids))
        profile.save()

        messages.success(request, 'Profile updated.')
        return redirect('accounts_profile')

    ctx = {
        'profile': profile,
        'all_tools': all_tools,
        'selected_tool_ids': set(profile.preferred_stack.values_list('id', flat=True)),
    }
    return render(request, 'accounts/profile.html', ctx)


@require_POST
@login_required
def toggle_saved_job(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    profile = request.user.userprofile
    if profile.saved_jobs.filter(id=job_id).exists():
        profile.saved_jobs.remove(job)
        saved = False
    else:
        profile.saved_jobs.add(job)
        saved = True
    return JsonResponse({'saved': saved, 'count': profile.saved_jobs.count()})
