from django.urls import path
from . import views

urlpatterns = [
    path('', views.job_list, name='job_list'),
    path('job/<int:job_id>/', views.job_detail, name='job_detail'),
    
    # New Post Job Routes
    path('post-job/', views.post_job, name='post_job'),
    path('post-job/success/', views.post_job_success, name='post_job_success'),
    
    path('subscribe/', views.subscribe, name='subscribe'),
    
    # Review Queue (Admin)
    path('staff/review/', views.review_queue, name='review_queue'),
    path('staff/review/<int:job_id>/<str:action>/', views.review_action, name='review_action'),
]
