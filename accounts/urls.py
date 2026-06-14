from django.urls import path, include
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='accounts_dashboard'),
    path('saved-jobs/', views.saved_jobs, name='accounts_saved_jobs'),
    path('profile/', views.profile_edit, name='accounts_profile'),
    path('saved-jobs/toggle/<int:job_id>/', views.toggle_saved_job, name='toggle_saved_job'),
    path('', include('allauth.urls')),
]
