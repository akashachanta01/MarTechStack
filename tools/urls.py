from django.urls import path
from . import views

urlpatterns = [
    # --- EXISTING TOOLS ---
    path('job-description-generator/', views.jd_generator, name='jd_generator'),
    path('api/generate-jd/', views.api_generate_jd, name='api_generate_jd'),
    path('salary-calculator/', views.salary_calculator, name='salary_calculator'),
    path('interview-questions-generator/', views.interview_generator, name='interview_generator'),
    path('api/generate-interview/', views.api_generate_interview, name='api_generate_interview'),
    path('hubspot-email-signature-generator/', views.signature_generator, name='signature_generator'),
    path('salesforce-id-converter/', views.sf_id_converter, name='sf_id_converter'),

    # --- NEW TOOLS ---
    path('qr-code-generator/', views.qr_generator, name='qr_generator'),
    path('utm-link-builder/', views.utm_builder, name='utm_builder'),
    path('sql-generator/', views.sql_generator, name='sql_generator'),
    path('api/generate-sql/', views.api_generate_sql, name='api_generate_sql'),
    path('consultant-rate-calculator/', views.consultant_calculator, name='consultant_calculator'),
    path('resume-keyword-scanner/', views.resume_scanner, name='resume_scanner'),
    path('api/scan-resume/', views.api_scan_resume, name='api_scan_resume'),

    # Dynamic Matcher (LAST)
    path('<slug:slug>/', views.jd_generator, name='tool_dynamic'),

]
