"""
Django Admin registrations for the agents app.

Provides a management UI at /admin/ for Agent, AgentVersion, Node, and Edge
records. This is new functionality not present in the FastAPI backend.
"""
from django.contrib import admin
from .models import Agent, AgentVersion, Edge, Node


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    """Admin view for Agent records."""
    list_display = ["id", "name", "status", "created_at", "updated_at"]
    list_filter = ["status"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]


@admin.register(AgentVersion)
class AgentVersionAdmin(admin.ModelAdmin):
    """Admin view for AgentVersion records."""
    list_display = ["id", "agent", "version_number", "entry_node", "created_at"]
    list_filter = ["agent"]
    search_fields = ["entry_node"]
    readonly_fields = ["created_at"]
    # raw_id_fields avoids loading all agents into a dropdown for large datasets
    raw_id_fields = ["agent", "created_from_version"]
    ordering = ["-created_at"]


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    """Admin view for Node records."""
    list_display = ["id", "name", "type", "subtype", "agent", "version", "created_at"]
    list_filter = ["type", "subtype"]
    search_fields = ["name"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["agent", "version"]
    ordering = ["-created_at"]


@admin.register(Edge)
class EdgeAdmin(admin.ModelAdmin):
    """Admin view for Edge records."""
    list_display = ["id", "agent", "version", "source_node_id", "target_node_id", "edge_type"]
    list_filter = ["edge_type"]
    raw_id_fields = ["agent", "version"]
    ordering = ["-created_at"]
