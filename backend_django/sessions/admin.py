"""Django Admin registration for the AgentSession model."""
from django.contrib import admin
from .models import AgentSession


@admin.register(AgentSession)
class AgentSessionAdmin(admin.ModelAdmin):
    """Admin view for AgentSession records."""
    list_display = ["id", "agent", "version", "created_at", "updated_at"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["agent", "version"]
    ordering = ["-created_at"]
