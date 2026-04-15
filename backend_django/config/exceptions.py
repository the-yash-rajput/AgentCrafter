"""
Custom DRF exception handler.

Replaces the @translate_service_errors decorator used in the FastAPI backend
(api/error_handling.py). Maps service-layer exceptions to the correct HTTP
status codes so the React frontend receives the same error shapes as before.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from services.exceptions import ConflictError, NotFoundError, ServiceError, ValidationError


def custom_exception_handler(exc, context):
    """
    Convert service-layer exceptions to DRF Responses.

    Falls back to DRF's built-in handler for all other exceptions so that
    serializer validation errors, authentication errors, etc. are still
    handled correctly.
    """
    # Map our domain exceptions → HTTP status codes
    if isinstance(exc, NotFoundError):
        return Response({"detail": exc.detail}, status=status.HTTP_404_NOT_FOUND)
    if isinstance(exc, ValidationError):
        return Response({"detail": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, ConflictError):
        return Response({"detail": exc.detail}, status=status.HTTP_409_CONFLICT)
    if isinstance(exc, ServiceError):
        return Response({"detail": exc.detail}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Delegate everything else (DRF serializer errors, 404s, etc.) to DRF
    return exception_handler(exc, context)
