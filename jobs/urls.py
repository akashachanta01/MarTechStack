from django.urls import path
from . import views

urlpatterns = [
    path('', views.job_list, name='job_list'),
    
    # --- STATIC PAGES ---
    path('about/', views.about, name='about'),
    path('for-employers/', views.for_employers, name='for_employers'),

    # --- STANDARD SEO: TOOL LANDING PAGES ---
    path('stack/<slug:slug>/', views.tool_detail, name='tool_detail'),
    
    # --- SEO: JOB DETAIL PAGE ---
    path('job/<int:id>/<slug:slug>/', views.job_detail, name='job_detail'),

    path('post-job/', views.post_job, name='post_job'),
    path('post-job/success/', views.post_job_success, name='post_job_success'),
    
    # Stripe Webhook
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
    
    path('subscribe/', views.subscribe, name='subscribe'),
    path('unsubscribe/', views.unsubscribe, name='unsubscribe'),

    path('staff/review/', views.review_queue, name='review_queue'),
    path('staff/review/<int:job_id>/<str:action>/', views.review_action, name='review_action'),

    # --- PROGRAMMATIC SEO (Must be last) ---
    # Matches: /remote/hubspot-jobs/ or /new-york/salesforce-jobs/
    path('<str:location_slug>/<slug:tool_slug>-jobs/', views.seo_landing_page, name='seo_tool_loc'),
    
    # Matches: /remote/jobs/ or /london/jobs/
    path('<str:location_slug>/jobs/', views.seo_landing_page, name='seo_loc_only'),
]
