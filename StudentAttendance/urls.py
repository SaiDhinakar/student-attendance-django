"""
URL configuration for StudentAttendance project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

def home_redirect(request):
    """Redirect to auth dashboard which handles role-based redirects"""
    if request.user.is_authenticated:
        return redirect('auth:dashboard')
    else:
        return redirect('auth:login')

urlpatterns = [
    path("admin/", admin.site.urls),
    path("admin_manager/", include("admin_management.urls")),  # Admin management endpoints
    path("", home_redirect, name="home"),  # Role-based redirect
    path("auth/", include("Authentication.urls")),  # Keep auth URLs for login
    path("staff/", include("attendance_dashboard.urls")),  # Staff attendance dashboard
    path("advisor/", include("advisor_dashboard.urls")),  # Advisor dashboard
    path("api/", include("core.urls")),  # Core API endpoints
    path("api/prediction/", include("prediction_backend.urls")),  # Prediction API
    # TODO: Add URL patterns for core app models when views are created
    # path("departments/", include("departments.urls")),
    # path("students/", include("students.urls")),
    # path("batches/", include("batches.urls")),
    # path("subjects/", include("subjects.urls")),
    # path("attendance/", include("attendance.urls")),
]
