from django.urls import path
from .views import login_view, logout_view, dashboard, departments, students, batches, subjects

urlpatterns = [
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("", dashboard, name="dashboard"),
    path("departments/", departments, name="departments"),
    path("students/", students, name="students"),
    path("batches/", batches, name="batches"),
    path("subjects/", subjects, name="subjects"),
]
