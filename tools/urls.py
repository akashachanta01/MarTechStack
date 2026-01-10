from django.urls import path
from . import views

urlpatterns = [
    # --- 1. JOB DESCRIPTION TOOLS ---
    path('job-description-generator/', views.jd_generator, name='jd_generator'),
    path('api/generate-jd/', views.api_generate_jd, name='api_generate_jd'),

    # --- 2. SALARY TOOLS ---
    path('salary-calculator/', views.salary_calculator, name='salary_calculator'),

    # --- 3. INTERVIEW TOOLS ---
    path('interview-questions-generator/', views.interview_generator, name='interview_generator'),
    path('api/generate-interview/', views.api_generate_interview, name='api_generate_interview'),

    # --- 4. NEW: HUBSPOT TOOLS (High Volume) ---
    path('hubspot-email-signature-generator/', views.signature_generator, name='signature_generator'),

    # --- 5. NEW: SALESFORCE TOOLS (High Retention) ---
    path('salesforce-id-converter/', views.sf_id_converter, name='sf_id_converter'),

    # --- DYNAMIC SLUG MATCHER (Must be last) ---
    path('<slug:slug>/', views.jd_generator, name='tool_dynamic'),
]
