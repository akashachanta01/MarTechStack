import json
import os
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from openai import OpenAI
from .models import ToolPage
# ADDED: Import Job model to fetch listings
from jobs.models import Job 

# --- 1. JOB DESCRIPTION GENERATOR ---
def jd_generator(request, slug=None):
    context = {
        'role_title': "Marketing Operations Manager",
        'responsibilities': [
            "Manage and optimize the marketing technology stack (Marketo, Salesforce)",
            "Oversee lead scoring, routing, and attribution models",
            "Ensure data hygiene and compliance (GDPR/CCPA)",
            "Build scalable workflows for campaign execution"
        ],
        'skills': [
            "3+ years in Marketing Ops or Demand Gen",
            "Proficiency in SQL and Data Visualization (Tableau/Looker)",
            "Experience with CRM integration (Salesforce/HubSpot)",
            "Strong analytical skills and attention to detail"
        ]
    }
    if slug:
        tool = get_object_or_404(ToolPage, slug=slug)
        context['role_title'] = tool.role_name
        if tool.default_responsibilities:
            context['responsibilities'] = [line.strip() for line in tool.default_responsibilities.split('\n') if line.strip()]
        if tool.default_skills:
            context['skills'] = [line.strip() for line in tool.default_skills.split('\n') if line.strip()]
        context['seo_title'] = tool.seo_title
        context['seo_description'] = tool.seo_description

    return render(request, 'tools/jd_generator.html', context)

@require_POST
def api_generate_jd(request):
    try:
        data = json.loads(request.body)
        role = data.get('role')
        stack = data.get('stack')
        seniority = data.get('seniority')
        tone = data.get('tone')

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key: return JsonResponse({"error": "API Key missing"}, status=500)

        client = OpenAI(api_key=api_key)
        prompt = f"Write a job description for a {seniority} {role}. Tech Stack: {stack}. Tone: {tone}. Output HTML with <h3> headers."
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are an expert HR recruiter."}, {"role": "user", "content": prompt}]
        )
        return JsonResponse({"html": completion.choices[0].message.content})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

# --- 2. SALARY CALCULATOR ---
def salary_calculator(request):
    return render(request, 'tools/salary_calculator.html', {
        'seo_title': "MarTech Salary Calculator 2026 - Real-time Market Data",
        'seo_description': "Calculate your market value in Marketing Operations. Data based on role, experience, and tech stack proficiency."
    })

# --- 3. INTERVIEW GENERATOR ---
def interview_generator(request):
    return render(request, 'tools/interview_generator.html', {
        'seo_title': "MarTech Interview Question Generator",
        'seo_description': "Generate technical interview questions for Salesforce, HubSpot, and Marketo roles. Perfect for hiring managers and candidates."
    })

@require_POST
def api_generate_interview(request):
    try:
        data = json.loads(request.body)
        role = data.get('role')
        stack = data.get('stack')
        difficulty = data.get('difficulty')

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key: return JsonResponse({"error": "API Key missing"}, status=500)

        client = OpenAI(api_key=api_key)
        prompt = f"""
        Generate 5 technical interview questions for a {role} specializing in {stack}.
        Difficulty: {difficulty}.
        Include 1 "Scenario-based" question.
        Output format (HTML):
        <ul>
            <li><strong>Question 1:</strong> [Question text]</li>
            ...
        </ul>
        """
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a technical hiring manager for Marketing Operations."}, {"role": "user", "content": prompt}]
        )
        return JsonResponse({"html": completion.choices[0].message.content})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

# --- 4. SIGNATURE GENERATOR ---
def signature_generator(request):
    return render(request, 'tools/signature_generator.html', {
        'seo_title': "Free HubSpot Email Signature Generator | Professional Templates",
        'seo_description': "Create a professional email signature for HubSpot, Gmail, and Outlook. Free tool for marketers and sales pros."
    })

# --- 5. SALESFORCE ID CONVERTER (UPDATED) ---
def sf_id_converter(request):
    # FETCH 5 LATEST SALESFORCE JOBS
    salesforce_jobs = Job.objects.filter(
        is_active=True,
        screening_status='approved',
        title__icontains='Salesforce'
    ).order_by('-created_at')[:5]

    return render(request, 'tools/sf_id_converter.html', {
        'seo_title': "Salesforce 15 to 18 Character ID Converter | MarTechJobs",
        'seo_description': "Convert Salesforce 15-character case-sensitive IDs to 18-character case-insensitive IDs. Essential for Admins doing data migration or VLOOKUPs.",
        'jobs': salesforce_jobs
    })

# --- 6. CONSULTANT RATE CALCULATOR ---
def consultant_calculator(request):
    return render(request, 'tools/rate_calculator.html', {
        'seo_title': "Freelance MarTech Consultant Rate Calculator",
        'seo_description': "Calculate your hourly rate as a HubSpot, Salesforce, or Marketo consultant. Based on market demand and experience."
    })

# --- 7. QR CODE GENERATOR ---
def qr_generator(request):
    return render(request, 'tools/qr_generator.html', {
        'seo_title': "Free HubSpot QR Code Generator with UTM Tracking",
        'seo_description': "Generate trackable QR codes for your marketing campaigns. Built-in UTM builder for HubSpot and Google Analytics tracking."
    })

# --- 8. UTM BUILDER ---
def utm_builder(request):
    return render(request, 'tools/utm_builder.html', {
        'seo_title': "Bulk UTM Link Builder for Marketers",
        'seo_description': "The fastest way to build Google Analytics tracking links. Save your presets for consistency across your team."
    })

# --- 9. TEXT TO SQL ---
def sql_generator(request):
    return render(request, 'tools/sql_generator.html', {
        'seo_title': "AI Text-to-SQL Generator for Marketing Data",
        'seo_description': "Convert plain English into SQL queries for Salesforce Data Cloud, Snowflake, and BigQuery. No coding required."
    })

@require_POST
def api_generate_sql(request):
    try:
        data = json.loads(request.body)
        query = data.get('query')
        flavor = data.get('flavor') 

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key: return JsonResponse({"error": "API Key missing"}, status=500)

        client = OpenAI(api_key=api_key)
        prompt = f"""
        You are an expert Data Engineer. Convert this marketing question into a SQL query.
        SQL Flavor: {flavor}
        Question: "{query}"
        
        Return ONLY the raw SQL code block. Do not wrap it in markdown ticks.
        Format it for readability.
        """
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a SQL expert."}, {"role": "user", "content": prompt}]
        )
        return JsonResponse({"sql": completion.choices[0].message.content.strip()})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

# --- 10. RESUME SCANNER ---
def resume_scanner(request):
    return render(request, 'tools/resume_scanner.html', {
        'seo_title': "Free ATS Resume Scanner for Marketing Ops",
        'seo_description': "Check your resume against MarTech job descriptions. Find missing keywords like SQL, Marketo, and API integration."
    })

@require_POST
def api_scan_resume(request):
    try:
        data = json.loads(request.body)
        resume_text = data.get('resume_text', '')
        target_role = data.get('target_role', 'Marketing Operations Manager')

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key: return JsonResponse({"error": "API Key missing"}, status=500)

        client = OpenAI(api_key=api_key)
        
        prompt = f"""
        Act as an ATS (Applicant Tracking System) for a {target_role} role.
        
        Analyze this resume text:
        "{resume_text[:3000]}"
        
        Identify:
        1. A Match Score (0-100)
        2. 3 Critical Missing Keywords (Technical skills only, e.g. SQL, Marketo, Python)
        3. 1 Actionable Improvement Tip
        
        Output JSON: {{ "score": 85, "missing": ["SQL", "Looker"], "tip": "..." }}
        """
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        return JsonResponse(json.loads(completion.choices[0].message.content))
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

# --- 11. ROAS CALCULATOR ---
def roas_calculator(request):
    return render(request, 'tools/roas_calculator.html', {
        'seo_title': "Free ROAS Calculator (Return on Ad Spend)",
        'seo_description': "Calculate your Return on Ad Spend (ROAS) instantly. Essential tool for Paid Search, Social, and Performance Marketers."
    })

# --- 12. EMAIL SUBJECT LINE TESTER ---
def subject_line_tester(request):
    return render(request, 'tools/subject_line_tester.html', {
        'seo_title': "AI Email Subject Line Tester & Grader",
        'seo_description': "Will your email get opened? Test your subject line against millions of data points using AI. Get a score and improvement tips."
    })

@require_POST
def api_test_subject_line(request):
    try:
        data = json.loads(request.body)
        subject = data.get('subject', '')

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key: return JsonResponse({"error": "API Key missing"}, status=500)

        client = OpenAI(api_key=api_key)
        
        prompt = f"""
        Act as a World-Class Email Marketing Copywriter (like Chase Dimond or Drayton Bird).
        Analyze this email subject line: "{subject}"
        
        Provide a JSON response with:
        1. "score": 0-100 integer.
        2. "grade": "A", "B", "C", "D", or "F".
        3. "feedback": One concise sentence on why it's good or bad.
        4. "better_versions": A list of 3 alternative, higher-converting variations.
        
        Strict JSON format.
        """
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        return JsonResponse(json.loads(completion.choices[0].message.content))
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
