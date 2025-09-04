from django.urls import path
from .views import login_view, logout_view, dashboard, notification_test

app_name = 'auth'

urlpatterns = [
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("", dashboard, name="dashboard"),  # Redirects based on user role
    path("test-notifications/", notification_test, name="notification_test"),  # Test page
]
