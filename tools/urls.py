from django.urls import path
from . import views

urlpatterns = [
    # The SEO Landing Pages (Visual)
    path('job-description-generator/', views.jd_generator, name='jd_generator'),
    path('<slug:slug>/', views.jd_generator, name='tool_dynamic'),

    # The Logic Engine (Hidden API)
    path('api/generate-jd/', views.api_generate_jd, name='api_generate_jd'),
]
