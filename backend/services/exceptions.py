from __future__ import annotations


class ServiceError(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class NotFoundError(ServiceError):
    pass


class ValidationError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass
