from django.urls import path
from . import views

urlpatterns = [
    path("", views.job_list, name="job_list"),
    path("job/<int:job_id>/", views.job_detail, name="job_detail"),
    path("post-job/", views.post_job, name="post_job"),
    path("subscribe/", views.subscribe, name="subscribe"),

    # Zero-Noise review tools (staff-only)
    path("review/", views.review_queue, name="review_queue"),
    path("review/<int:job_id>/<str:action>/", views.review_action, name="review_action"),
]
