from django.urls import path
from . import views

app_name = 'attendance_dashboard'

urlpatterns = [
    path('', views.staff_dashboard, name='dashboard'),
    path('attendance/', views.attendance_view, name='attendance'),
    path('camera/', views.camera_attendance_view, name='camera_attendance'),
    path('reports/', views.reports_view, name='reports'),
]
