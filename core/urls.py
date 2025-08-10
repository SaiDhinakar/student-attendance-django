from django.urls import path
from .api_views import AttendanceFormAPIView, TimeBlocksAPIView

app_name = 'core_api'

urlpatterns = [
    path('attendance-form/', AttendanceFormAPIView.as_view(), name='attendance_form_api'),
    path('time-blocks/', TimeBlocksAPIView.as_view(), name='time_blocks_api'),
]
