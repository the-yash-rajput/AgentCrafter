from __future__ import annotations

from typing import Any


class ServiceError(Exception):
    def __init__(self, detail: Any):
        super().__init__(detail)
        self.detail = detail


class NotFoundError(ServiceError):
    pass


class ValidationError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass


class PauseRequestedError(Exception):
    """Raised between graph nodes when pause_requested=True is detected."""
