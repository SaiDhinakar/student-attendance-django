from django.urls import path
from . import views

app_name = 'admin_management'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('update/', views.update_server, name='update_server'),
    path('status/', views.update_status, name='update_status'),
]
