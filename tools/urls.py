from django.urls import path
from . import views

urlpatterns = [
    # --- EXISTING TOOLS ---
    path('job-description-generator/', views.jd_generator, name='jd_generator'),
    path('api/generate-jd/', views.api_generate_jd, name='api_generate_jd'),

    # --- NEW: SALARY CALCULATOR ---
    path('salary-calculator/', views.salary_calculator, name='salary_calculator'),

    # --- NEW: INTERVIEW GENERATOR ---
    path('interview-questions-generator/', views.interview_generator, name='interview_generator'),
    path('api/generate-interview/', views.api_generate_interview, name='api_generate_interview'),

    # Dynamic Slug Matcher (Keep this last)
    path('<slug:slug>/', views.jd_generator, name='tool_dynamic'),
]
