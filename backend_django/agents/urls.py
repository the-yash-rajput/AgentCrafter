"""
URL patterns for the agents app.

All paths are mounted under /api/ in config/urls.py, so these patterns are
relative to that prefix.

IMPORTANT ordering rule: static path segments (e.g. "agents/import",
"node-definitions") must appear BEFORE parameterized paths (e.g.
"agents/<int:agent_id>") so that Django's sequential resolver doesn't
mistake the static segment for an integer parameter.
"""
from django.urls import path
from . import views

urlpatterns = [
    # ── Node definitions ──────────────────────────────────────────────────────
    # Must be before any agents/<id>/nodes routes.
    path("node-definitions", views.NodeDefinitionsView.as_view()),

    # ── Agent import ──────────────────────────────────────────────────────────
    # Must be before agents/<agent_id> or "import" is parsed as an integer.
    path("agents/import", views.AgentImportView.as_view()),

    # ── Agent CRUD ────────────────────────────────────────────────────────────
    path("agents", views.AgentListCreateView.as_view()),
    path("agents/<int:agent_id>", views.AgentDetailView.as_view()),
    path("agents/<int:agent_id>/duplicate", views.AgentDuplicateView.as_view()),

    # ── Versions ──────────────────────────────────────────────────────────────
    path("agents/<int:agent_id>/versions", views.VersionListView.as_view()),
    path("agents/<int:agent_id>/versions/<int:version_id>", views.VersionDetailView.as_view()),
    path("agents/<int:agent_id>/versions/<int:version_id>/fork", views.VersionForkView.as_view()),
    path("agents/<int:agent_id>/versions/<int:version_id>/export", views.VersionExportView.as_view()),

    # ── Nodes (version-scoped create) ─────────────────────────────────────────
    path("agents/<int:agent_id>/nodes", views.NodeListCreateView.as_view()),
    path("agents/<int:agent_id>/versions/<int:version_id>/nodes", views.VersionNodeCreateView.as_view()),
    path("nodes/<int:node_id>", views.NodeDetailView.as_view()),

    # ── Edges (version-scoped create) ─────────────────────────────────────────
    path("agents/<int:agent_id>/edges", views.EdgeListCreateView.as_view()),
    path("agents/<int:agent_id>/versions/<int:version_id>/edges", views.VersionEdgeCreateView.as_view()),
    path("edges/<int:edge_id>", views.EdgeDetailView.as_view()),

    # ── Langfuse ──────────────────────────────────────────────────────────────
    path("langfuse/prompts", views.LangfusePromptsView.as_view()),
]
