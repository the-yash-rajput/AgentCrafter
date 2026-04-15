"""
URL patterns for the runs app.

All patterns are mounted under /api/ in config/urls.py.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Validation — must be before /runs/<run_id> to avoid ambiguity
    path("agents/<int:agent_id>/validate", views.AgentValidateView.as_view()),

    # Run list and detail
    path("agents/<int:agent_id>/runs", views.RunListView.as_view()),
    path("runs/<int:run_id>", views.RunDetailView.as_view()),

    # SSE streaming endpoint
    path("runs/<int:run_id>/stream", views.RunStreamView.as_view()),
]
