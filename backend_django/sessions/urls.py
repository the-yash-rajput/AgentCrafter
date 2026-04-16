"""
URL patterns for the sessions app.

All patterns are mounted under /api/ in config/urls.py.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Session list + create (for a specific agent version)
    path(
        "agents/<int:agent_id>/versions/<int:version_id>/sessions",
        views.SessionListCreateView.as_view(),
    ),
    # Session detail (get conversation history)
    path(
        "agents/<int:agent_id>/versions/<int:version_id>/sessions/<int:session_id>",
        views.SessionDetailView.as_view(),
    ),
    # Execute a turn within a session
    path(
        "agents/<int:agent_id>/versions/<int:version_id>/sessions/<int:session_id>/run",
        views.SessionRunView.as_view(),
    ),
]
