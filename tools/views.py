import json
import os
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from openai import OpenAI
from .models import ToolPage

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

# --- 4. NEW: SIGNATURE GENERATOR ---
def signature_generator(request):
    return render(request, 'tools/signature_generator.html', {
        'seo_title': "Free HubSpot Email Signature Generator | Professional Templates",
        'seo_description': "Create a professional email signature for HubSpot, Gmail, and Outlook. Free tool for marketers and sales pros."
    })

# --- 5. NEW: SALESFORCE ID CONVERTER ---
def sf_id_converter(request):
    return render(request, 'tools/sf_id_converter.html', {
        'seo_title': "Salesforce 15 to 18 Character ID Converter",
        'seo_description': "Convert Salesforce 15-character case-sensitive IDs to 18-character case-insensitive IDs instantly. Essential for Admins."
    })
    # --- 6. NEW: CONSULTANT RATE CALCULATOR ---
def rate_calculator(request):
    return render(request, 'tools/rate_calculator.html', {
        'seo_title': "Freelance MarTech Consultant Rate Calculator",
        'seo_description': "Calculate your hourly rate as a HubSpot, Salesforce, or Marketo consultant. Based on market demand and experience."
    })

# --- 7. NEW: UTM BUILDER ---
def utm_builder(request):
    return render(request, 'tools/utm_builder.html', {
        'seo_title': "Google Analytics Campaign URL Builder (UTM Generator)",
        'seo_description': "Easily build tracking URLs for your marketing campaigns. The cleanest UTM builder for Marketing Ops pros."
    })
