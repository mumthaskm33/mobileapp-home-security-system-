from django.urls import path
from .views import (
    camera_page,
    register_face_api,
    recognize_face_api,
    register_page,
    logs_page,
    authorized_page,
    clear_logs_api,
    delete_user_api
)

urlpatterns = [
    path("", camera_page, name="camera"),
    path("register/", register_page, name="register"),
    path("logs/", logs_page, name="logs"),
    path("authorized/", authorized_page, name="authorized"),
    path("api/register/", register_face_api),
    path("api/recognize/", recognize_face_api),
    path("api/clear_logs/", clear_logs_api),
    path("api/delete_user/<int:user_id>/", delete_user_api),
]

# Force reload
