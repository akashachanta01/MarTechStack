from django.shortcuts import render, get_object_or_404
from .models import ToolPage

def jd_generator(request, slug=None):
    # Default content if no database object exists yet
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

    # If we have a specific DB object (for SEO pages like /tools/hubspot-admin-jd/)
    if slug:
        tool = get_object_or_404(ToolPage, slug=slug)
        context['role_title'] = tool.role_name
        # Split text fields by newline to create lists
        if tool.default_responsibilities:
            context['responsibilities'] = [line.strip() for line in tool.default_responsibilities.split('\n') if line.strip()]
        if tool.default_skills:
            context['skills'] = [line.strip() for line in tool.default_skills.split('\n') if line.strip()]
        
        context['seo_title'] = tool.seo_title
        context['seo_description'] = tool.seo_description

    return render(request, 'tools/jd_generator.html', context)
