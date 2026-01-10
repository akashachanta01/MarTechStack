from django.urls import path
from . import views

urlpatterns = [
    # Main Generator (Generic)
    path('job-description-generator/', views.jd_generator, name='jd_generator'),
    
    # Programmatic Pages (e.g. /tools/hubspot-admin-job-description/)
    path('<slug:slug>/', views.jd_generator, name='tool_dynamic'),
]
