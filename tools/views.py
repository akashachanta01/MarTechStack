import json
import os
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from openai import OpenAI
from .models import ToolPage

# --- 1. THE PAGE RENDERER (SEO) ---
def jd_generator(request, slug=None):
    # Default SEO content (Fallback)
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

    # If this is a specific SEO landing page (e.g. /tools/hubspot-admin/)
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

# --- 2. THE AI GENERATOR (API) ---
@require_POST
def api_generate_jd(request):
    try:
        data = json.loads(request.body)
        role = data.get('role')
        stack = data.get('stack')
        seniority = data.get('seniority')
        tone = data.get('tone')

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return JsonResponse({"error": "Server configuration error (API Key missing)"}, status=500)

        client = OpenAI(api_key=api_key)

        prompt = f"""
        Write a job description for a {seniority} {role}.
        Tech Stack involved: {stack if stack else 'General MarTech Stack'}.
        Tone: {tone}.
        
        Output format (HTML):
        <h3>About the Role</h3>
        <p>[2 sentences hook]</p>
        <h3>Responsibilities</h3>
        <ul>[5 bullet points]</ul>
        <h3>Requirements</h3>
        <ul>[5 bullet points]</ul>
        """

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert HR recruiter for Marketing Technology."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        content = completion.choices[0].message.content
        # Strip markdown code blocks if present
        content = content.replace("```html", "").replace("```", "")

        return JsonResponse({"html": content})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
