from __future__ import annotations

from functools import wraps
from inspect import iscoroutinefunction

from fastapi import HTTPException

from services.exceptions import ConflictError, NotFoundError, ServiceError, ValidationError


def service_error_to_http_exception(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=exc.detail)
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=409, detail=exc.detail)
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=400, detail=exc.detail)
    return HTTPException(status_code=500, detail=exc.detail)


def translate_service_errors(func):
    if iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except ServiceError as exc:
                raise service_error_to_http_exception(exc) from exc

        return async_wrapper

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ServiceError as exc:
            raise service_error_to_http_exception(exc) from exc

    return wrapper
