from django.apps import AppConfig


class SessionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sessions"
    # Avoid clash with Django's built-in django.contrib.sessions app label.
    label = "agent_sessions"
