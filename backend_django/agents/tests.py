"""
Agent app tests.

The existing service-layer tests in tests/ are migrated to pytest-django.
Integration tests using the Django test client are added here.
For unit tests see tests/test_run_service.py etc. (copied from FastAPI backend).
"""
from django.test import TestCase


class AgentViewsTestCase(TestCase):
    """Placeholder — add Django TestClient-based integration tests here."""
    pass
