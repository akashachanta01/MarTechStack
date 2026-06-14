import json
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

from jobs.models import Job, Tool
from .models import UserProfile
from .emails import send_pro_waitlist_alert


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
        'pro_waitlist': profile.pro_waitlist,
    }
    return render(request, 'accounts/dashboard.html', ctx)


@require_POST
@login_required
def join_pro_waitlist(request):
    profile = request.user.userprofile
    if not profile.pro_waitlist:
        profile.pro_waitlist = True
        profile.pro_waitlist_at = timezone.now()
        profile.save(update_fields=['pro_waitlist', 'pro_waitlist_at', 'updated_at'])
        send_pro_waitlist_alert(request.user)  # internally non-fatal
    return JsonResponse({'ok': True})


@login_required
def saved_jobs(request):
    profile = request.user.userprofile
    jobs = profile.saved_jobs.filter(is_active=True).order_by('-created_at')
    return render(request, 'accounts/saved_jobs.html', {'saved_jobs': jobs})


def _clean_url(raw):
    """Normalise a user-entered URL to https and reject non-http(s) schemes
    (javascript:, ftp:, etc). Returns '' for blank/invalid. URLField validators
    don't run on .save(), so we validate here."""
    raw = (raw or '').strip()
    if not raw:
        return ''
    if raw.startswith('http://'):
        raw = 'https://' + raw[len('http://'):]
    elif not raw.startswith('https://'):
        raw = 'https://' + raw
    try:
        URLValidator(schemes=['https'])(raw)
    except ValidationError:
        return ''
    return raw[:200]


@login_required
def profile_edit(request):
    profile = request.user.userprofile
    all_tools = Tool.objects.order_by('name')

    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '').strip()[:30]
        request.user.last_name = request.POST.get('last_name', '').strip()[:150]
        request.user.save()

        profile.bio = request.POST.get('bio', '').strip()[:1000]
        profile.preferred_location = request.POST.get('preferred_location', '').strip()[:100]
        # Social links
        profile.linkedin_url = _clean_url(request.POST.get('linkedin_url'))
        profile.github_url = _clean_url(request.POST.get('github_url'))
        profile.twitter_url = _clean_url(request.POST.get('twitter_url'))
        profile.website_url = _clean_url(request.POST.get('website_url'))
        # Preferences
        profile.open_to_remote = request.POST.get('open_to_remote') == 'on'
        role = request.POST.get('desired_role_type', '').strip()
        profile.desired_role_type = role if role in {'full_time', 'contract', 'part_time'} else ''
        profile.desired_salary = request.POST.get('desired_salary', '').strip()[:60]
        profile.preferred_stack.set(Tool.objects.filter(id__in=request.POST.getlist('preferred_stack')))
        profile.save()

        messages.success(request, 'Profile updated.')
        active = request.POST.get('active_tab', 'basic')
        return redirect(reverse('accounts_profile') + '#' + active)

    ctx = {
        'profile': profile,
        'all_tools': all_tools,
        'selected_tool_ids': set(profile.preferred_stack.values_list('id', flat=True)),
    }
    return render(request, 'accounts/profile.html', ctx)


@login_required
def settings_view(request):
    profile = request.user.userprofile
    has_google = request.user.socialaccount_set.filter(provider='google').exists()
    return render(request, 'accounts/settings.html', {
        'profile': profile,
        'has_google': has_google,
    })


@require_POST
@login_required
def update_notifications(request):
    """AJAX endpoint for the Settings notification toggles + quick actions."""
    profile = request.user.userprofile
    action = request.POST.get('action', '')
    if action == 'pause_all':
        profile.email_newsletter = False
        profile.email_announcements = False
    elif action == 'enable_all':
        profile.email_newsletter = True
        profile.email_announcements = True
    else:
        field = request.POST.get('field')
        value = request.POST.get('value') == 'true'
        if field == 'newsletter':
            profile.email_newsletter = value
        elif field == 'announcements':
            profile.email_announcements = value
    profile.save(update_fields=['email_newsletter', 'email_announcements', 'updated_at'])
    return JsonResponse({
        'ok': True,
        'newsletter': profile.email_newsletter,
        'announcements': profile.email_announcements,
    })


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
