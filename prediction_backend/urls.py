from django.urls import path
from . import views

app_name = 'prediction_backend'

urlpatterns = [
    path('process-images/', views.process_images, name='process_images'),
    path('submit-attendance/', views.submit_attendance, name='submit_attendance'),
    path('session/<str:session_id>/', views.get_session_data, name='get_session_data'),
    
    # Debug endpoints
    path('debug/temp/<str:session_id>/', views.debug_temp_directory, name='debug_temp_directory'),
    path('debug/temp-list/', views.list_all_temp_directories, name='list_all_temp_directories'),
    path('debug/attendance-records/', views.check_attendance_records, name='check_attendance_records'),
    path('debug/session/<str:session_id>/', views.debug_session_info, name='debug_session_info'),
]
