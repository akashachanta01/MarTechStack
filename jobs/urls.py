from django.urls import path
from django.views.generic import RedirectView
from . import views
from .feeds import LatestJobsFeed

urlpatterns = [
    path('', views.job_list, name='job_list'),
    
    # --- GROWTH ENGINE ---
    path('salary-guide/', views.salary_guide, name='salary_guide'),
    path('feed/', LatestJobsFeed(), name='job_feed'),
    
    # --- BLOG (DYNAMIC) ---
    path('blog/', views.blog_list, name='blog_list'),
    path('blog/<slug:slug>/', views.post_detail, name='post_detail'),

    # --- STATIC PAGES ---
    path('about/', views.about, name='about'),
    path('privacy/', views.privacy, name='privacy'),
    path('terms/', views.terms, name='terms'),
    path('for-employers/', views.for_employers, name='for_employers'),
    path('contact/', views.contact, name='contact'),

    # --- BROWSE ALL JOBS (Jobs nav destination) ---
    path('jobs/', views.all_jobs, name='all_jobs'),

    # --- SEO STRATEGY IMPLEMENTATION ---
    path('jobs/<slug:slug>/', views.tool_detail, name='tool_detail'),
    path('job/<int:id>/<slug:slug>/', views.job_detail, name='job_detail'),

    path('post-job/', views.post_job, name='post_job'),
    path('post-job/success/', views.post_job_success, name='post_job_success'),
    
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
    path('subscribe/', views.subscribe, name='subscribe'),
    path('unsubscribe/', views.unsubscribe, name='unsubscribe'),
    path('u/<str:token>/', views.unsubscribe_oneclick, name='unsubscribe_oneclick'),

    path('staff/review/', views.review_queue, name='review_queue'),
    path('staff/review/<int:job_id>/<str:action>/', views.review_action, name='review_action'),

    path('companies/', views.company_list, name='company_list'),
    path('companies/<str:company_slug>/', views.company_detail, name='company_detail'),

    # --- NEW: DIRECTORY (Fixes Orphan Pages) ---
    path('jobs-by-tool/', views.directory, name='directory'),
    # 301 the old /directory/ URL to the new SEO-friendly path
    path('directory/', RedirectView.as_view(pattern_name='directory', permanent=True)),

    # --- CATEGORY LANDING PAGES (Engineering / Operations / Data) ---
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),

    # --- JOB-TITLE PAGES (single-segment, curated titles only) ---
    path('<slug:title_slug>-jobs/', views.title_jobs, name='title_jobs'),

    # --- PROGRAMMATIC SEO (Must be last) ---
    path('<str:location_slug>/<slug:tool_slug>-jobs/', views.seo_landing_page, name='seo_tool_loc'),
    path('<str:location_slug>/jobs/', views.seo_landing_page, name='seo_loc_only'),
]
