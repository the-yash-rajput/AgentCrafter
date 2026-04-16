"""
Root URL configuration for AgentCrafter Django project.

All API routes are mounted under /api/ and delegated to each app's urls.py.
The URL paths exactly match the FastAPI router prefixes so the React frontend
requires zero changes.
"""
from django.contrib import admin
from django.urls import include, path
from rest_framework.response import Response
from rest_framework.decorators import api_view


@api_view(["GET"])
def health(request):
    """Health-check endpoint — mirrors GET /health in the FastAPI app."""
    return Response({"status": "ok", "service": "Agent Crafter"})


urlpatterns = [
    # Django admin panel (new in the Django version — not in the FastAPI backend)
    path("admin/", admin.site.urls),

    # API routes — each app registers its own patterns under /api/
    path("api/", include("agents.urls")),
    path("api/", include("runs.urls")),
    path("api/", include("sessions.urls")),

    # Health check
    path("health", health),
]
