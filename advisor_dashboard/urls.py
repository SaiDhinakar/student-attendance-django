from django.urls import path
from . import views

app_name = 'advisor_dashboard'

urlpatterns = [
    # Dashboard
    path('', views.advisor_dashboard, name='dashboard'),
    path('department-attendance/', views.department_attendance, name='department_attendance'),
    path('attendance/', views.advisor_attendance_marking, name='attendance'),
    
    # Report URLs
    path('reports/', views.attendance_reports, name='reports'),
    path('reports/daily/', views.daily_report, name='daily_report'),
    path('reports/weekly/', views.weekly_report, name='weekly_report'),
    path('reports/monthly/', views.monthly_report, name='monthly_report'),
    path('reports/subject/', views.subject_report, name='subject_report'),
    path('reports/custom/', views.custom_report, name='custom_report'),
    
    path('history/', views.advisor_attendance_history, name='attendance_history'),
    
    # Student CRUD operations
    path('students/', views.student_list, name='student_list'),
    path('students/create/', views.student_create, name='student_create'),
    path('students/bulk-upload/', views.bulk_student_upload, name='bulk_student_upload'),
    path('students/<str:student_regno>/', views.student_detail, name='student_detail'),
    path('students/<str:student_regno>/edit/', views.student_edit, name='student_edit'),
    path('students/<str:student_regno>/delete/', views.student_delete, name='student_delete'),
    
    # Subject operations
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/create/', views.subject_create, name='subject_create'),
    
    # Attendance CRUD operations
    path('attendance-records/', views.attendance_list, name='attendance_list'),
    path('attendance-records/<int:attendance_id>/edit/', views.attendance_edit, name='attendance_edit'),
    path('attendance-records/bulk-edit/', views.bulk_attendance_edit, name='bulk_attendance_edit'),
    
    # Staff attendance access
    path('staff-attendance/', views.staff_attendance_access, name='staff_attendance'),
    
    # API endpoints
    path('api/sections/', views.get_advisor_sections_api, name='api_sections'),
]
