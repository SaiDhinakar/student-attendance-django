from django.urls import path
from . import views

app_name = 'advisor_dashboard'

urlpatterns = [
    path('', views.advisor_dashboard, name='dashboard'),
    path('department-attendance/', views.department_attendance, name='department_attendance'),
    path('attendance/', views.advisor_attendance_marking, name='attendance'),
    path('reports/', views.advisor_reports, name='reports'),
]
