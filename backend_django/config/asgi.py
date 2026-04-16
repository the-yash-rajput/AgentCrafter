"""
ASGI config for AgentCrafter project.

Exposes the ASGI callable as a module-level variable named ``application``.
Use with uvicorn for SSE streaming support:
  uvicorn config.asgi:application --host 0.0.0.0 --port 8000
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()
