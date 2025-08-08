from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "Authentication"

    def ready(self):
        # Place for signals if needed in future
        pass
