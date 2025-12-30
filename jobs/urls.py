from django.urls import path
from . import views

urlpatterns = [
    path('', views.job_list, name='job_list'),
    
    # --- SEO: TOOL LANDING PAGES (Topic Clusters) ---
    path('stack/<slug:slug>/', views.tool_detail, name='tool_detail'),
    
    # --- SEO: JOB DETAIL PAGE ---
    path('job/<int:id>/<slug:slug>/', views.job_detail, name='job_detail'),

    path('post-job/', views.post_job, name='post_job'),
    path('post-job/success/', views.post_job_success, name='post_job_success'),
    
    # Stripe Webhook
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
    
    path('subscribe/', views.subscribe, name='subscribe'),
    
    # NEW: UNSUBSCRIBE
    path('unsubscribe/', views.unsubscribe, name='unsubscribe'),

    path('staff/review/', views.review_queue, name='review_queue'),
    path('staff/review/<int:job_id>/<str:action>/', views.review_action, name='review_action'),
]
