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
    path('consultant-rate-calculator/', views.rate_calculator, name='rate_calculator'),
    path('utm-builder/', views.utm_builder, name='utm_builder'),

    # --- DYNAMIC SLUG (Keep Last) ---
    path('<slug:slug>/', views.jd_generator, name='tool_dynamic'),
]
