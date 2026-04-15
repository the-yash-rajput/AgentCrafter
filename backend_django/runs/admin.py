"""Django Admin registration for the Run model."""
from django.contrib import admin
from .models import Run


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    """Admin view for Run records."""
    list_display = ["id", "agent", "status", "version", "session", "started_at", "completed_at"]
    list_filter = ["status"]
    search_fields = ["error"]
    readonly_fields = ["started_at", "completed_at"]
    raw_id_fields = ["agent", "version", "session"]
    ordering = ["-started_at"]
