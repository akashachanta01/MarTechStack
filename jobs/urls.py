from django.urls import path
from . import views

urlpatterns = [
    path('', views.job_list, name='job_list'),
    path('job/<int:pk>/', views.job_detail, name='job_detail'),
    path('post-job/', views.post_job, name='post_job'),
    path('subscribe/', views.subscribe, name='subscribe'), # New!
]
