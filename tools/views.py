import json
import os
import time
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q
from openai import OpenAI
from .models import ToolPage
from jobs.models import Job 

# --- SECURITY: API RATE LIMITER (Protects your OpenAI Wallet) ---
def check_rate_limit(request):
    current_time = time.time()
    
    # Check frequency (Cooldown: 5 seconds between clicks)
    last_call = request.session.get('last_ai_call', 0)
    if current_time - last_call < 5:
        return False, "Please wait a few seconds before generating again."
        
    # Check daily quota (Max 15 free generations per user per day)
    usage_count = request.session.get('ai_usage_count', 0)
    last_reset = request.session.get('ai_usage_reset', current_time)
    
    # Reset quota every 24 hours
    if current_time - last_reset > 86400:
        usage_count = 0
        request.session['ai_usage_reset'] = current_time
        
    if usage_count >= 15:
        return False, "You've hit your free daily limit for AI tools! Please come back tomorrow."
        
    # Update session
    request.session['last_ai_call'] = current_time
    request.session['ai_usage_count'] = usage_count + 1
    return True, ""


# --- 1. JOB DESCRIPTION GENERATOR ---
def jd_generator(request, slug=None):
    jobs = Job.objects.filter(is_active=True, screening_status='approved').filter(Q(title__icontains='Operations') | Q(title__icontains='Manager')).order_by('-created_at')[:5]
    context = {
        'role_title': "Marketing Operations Manager",
        'responsibilities': ["Manage and optimize the marketing technology stack", "Oversee lead scoring and routing", "Ensure data hygiene"],
        'skills': ["3+ years in Marketing Ops", "Proficiency in SQL", "CRM integration experience"],
        'jobs': jobs,
        'seo_title': "AI Job Description Generator for MarTech Roles",
        'seo_description': "Draft highly technical, customized Marketing Operations job descriptions in seconds."
    }
    if slug:
        tool = get_object_or_404(ToolPage, slug=slug)
        context['role_title'] = tool.role_name
        if tool.default_responsibilities: context['responsibilities'] = [line.strip() for line in tool.default_responsibilities.split('\n') if line.strip()]
        if tool.default_skills: context['skills'] = [line.strip() for line in tool.default_skills.split('\n') if line.strip()]
        context['seo_title'] = tool.seo_title; context['seo_description'] = tool.seo_description

    return render(request, 'tools/jd_generator.html', context)

@require_POST
def api_generate_jd(request):
    is_safe, error_msg = check_rate_limit(request)
    if not is_safe: return JsonResponse({"error": error_msg}, status=429)

    try:
        data = json.loads(request.body)
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key: return JsonResponse({"error": "API Key missing"}, status=500)

        client = OpenAI(api_key=api_key)
        prompt = f"Write a {data.get('seniority')} job description for a {data.get('role')} using {data.get('stack')}. Tone: {data.get('tone')}. Output HTML with <h3> headers."
        
        completion = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": "You are an expert HR recruiter."}, {"role": "user", "content": prompt}])
        return JsonResponse({"html": completion.choices[0].message.content})
    except Exception as e: return JsonResponse({"error": str(e)}, status=500)


# --- 2. SALARY CALCULATOR ---
def salary_calculator(request):
    jobs = Job.objects.filter(is_active=True, screening_status='approved').filter(Q(title__icontains='Director') | Q(title__icontains='Manager')).order_by('-created_at')[:5]
    return render(request, 'tools/salary_calculator.html', {'seo_title': "MarTech Salary Calculator 2026", 'seo_description': "Calculate your market value in Marketing Operations.", 'jobs': jobs})


# --- 3. INTERVIEW GENERATOR ---
def interview_generator(request):
    jobs = Job.objects.filter(is_active=True, screening_status='approved').filter(Q(title__icontains='Lead') | Q(title__icontains='Manager')).order_by('-created_at')[:5]
    return render(request, 'tools/interview_generator.html', {'seo_title': "MarTech Interview Question Generator", 'seo_description': "Generate technical interview questions.", 'jobs': jobs})

@require_POST
def api_generate_interview(request):
    is_safe, error_msg = check_rate_limit(request)
    if not is_safe: return JsonResponse({"error": error_msg}, status=429)

    try:
        data = json.loads(request.body)
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key: return JsonResponse({"error": "API Key missing"}, status=500)

        client = OpenAI(api_key=api_key)
        prompt = f"Generate 5 technical interview questions for a {data.get('role')} specializing in {data.get('stack')}. Difficulty: {data.get('difficulty')}. Output HTML list."
        completion = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": "You are a technical hiring manager."}, {"role": "user", "content": prompt}])
        return JsonResponse({"html": completion.choices[0].message.content})
    except Exception as e: return JsonResponse({"error": str(e)}, status=500)


# --- 4. TEXT TO SQL ---
def sql_generator(request):
    jobs = Job.objects.filter(is_active=True, screening_status='approved', title__icontains='SQL').order_by('-created_at')[:5]
    return render(request, 'tools/sql_generator.html', {'seo_title': "AI Text-to-SQL Generator for Marketing Data", 'seo_description': "Convert plain English into SQL queries.", 'jobs': jobs})

@require_POST
def api_generate_sql(request):
    is_safe, error_msg = check_rate_limit(request)
    if not is_safe: return JsonResponse({"error": error_msg}, status=429)

    try:
        data = json.loads(request.body)
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key: return JsonResponse({"error": "API Key missing"}, status=500)

        client = OpenAI(api_key=api_key)
        prompt = f"Convert to SQL ({data.get('flavor')}): '{data.get('query')}'. Return ONLY raw SQL code."
        completion = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": "You are a SQL expert."}, {"role": "user", "content": prompt}])
        return JsonResponse({"sql": completion.choices[0].message.content.strip()})
    except Exception as e: return JsonResponse({"error": str(e)}, status=500)


# --- 5. RESUME SCANNER ---
def resume_scanner(request):
    return render(request, 'tools/resume_scanner.html', {'seo_title': "Free ATS Resume Scanner for Marketing Ops", 'seo_description': "Check your resume against MarTech job descriptions."})

@require_POST
def api_scan_resume(request):
    is_safe, error_msg = check_rate_limit(request)
    if not is_safe: return JsonResponse({"error": error_msg}, status=429)

    try:
        data = json.loads(request.body)
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key: return JsonResponse({"error": "API Key missing"}, status=500)

        client = OpenAI(api_key=api_key)
        prompt = f"Act as ATS for {data.get('target_role')}. Analyze resume: '{data.get('resume_text', '')[:3000]}'. Output JSON: {{ 'score': 85, 'missing': ['SQL'], 'tip': '...' }}"
        completion = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"})
        return JsonResponse(json.loads(completion.choices[0].message.content))
    except Exception as e: return JsonResponse({"error": str(e)}, status=500)


# --- 6. SUBJECT LINE TESTER ---
def subject_line_tester(request):
    return render(request, 'tools/subject_line_tester.html', {'seo_title': "AI Email Subject Line Tester & Grader", 'seo_description': "Will your email get opened? Test your subject line."})

@require_POST
def api_test_subject_line(request):
    is_safe, error_msg = check_rate_limit(request)
    if not is_safe: return JsonResponse({"error": error_msg}, status=429)

    try:
        data = json.loads(request.body)
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key: return JsonResponse({"error": "API Key missing"}, status=500)

        client = OpenAI(api_key=api_key)
        prompt = f"Analyze email subject: '{data.get('subject')}'. JSON output: {{'score': int, 'grade': str, 'feedback': str, 'better_versions': [str]}}"
        completion = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": "You are a copywriter."}, {"role": "user", "content": prompt}], response_format={"type": "json_object"})
        return JsonResponse(json.loads(completion.choices[0].message.content))
    except Exception as e: return JsonResponse({"error": str(e)}, status=500)


# --- OTHER STATIC TOOLS ---
def signature_generator(request): return render(request, 'tools/signature_generator.html', {'seo_title': "HubSpot Email Signature Generator", 'seo_description': "Create a professional email signature."})
def sf_id_converter(request): return render(request, 'tools/sf_id_converter.html', {'seo_title': "Salesforce 15 to 18 Character ID Converter", 'seo_description': "Convert Salesforce IDs easily."})
def consultant_calculator(request): return render(request, 'tools/rate_calculator.html', {'seo_title': "Freelance MarTech Consultant Rate Calculator", 'seo_description': "Calculate your hourly rate."})
def qr_generator(request): return render(request, 'tools/qr_generator.html', {'seo_title': "HubSpot QR Code Generator", 'seo_description': "Generate trackable QR codes."})
def utm_builder(request): return render(request, 'tools/utm_builder.html', {'seo_title': "Bulk UTM Link Builder for Marketers", 'seo_description': "Build Google Analytics tracking links."})
def roas_calculator(request): return render(request, 'tools/roas_calculator.html', {'seo_title': "Free ROAS Calculator", 'seo_description': "Calculate Return on Ad Spend."})

# --- THE TOOLS HUB ---
def tools_hub(request):
    return render(request, 'tools/hub.html', {'seo_title': "Free MarTech Tools & Calculators | MarTechJobs", 'seo_description': "A curated suite of free tools for marketing operations professionals."})
