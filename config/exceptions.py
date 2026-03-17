"""Кастомный обработчик исключений DRF."""

from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.orders.exceptions import OrderError


def order_exception_handler(exc: Exception, context: dict) -> Response | None:
    """Преобразует OrderError в JSON-ответ с нужным HTTP-статусом."""
    if isinstance(exc, OrderError):
        return Response({"error": str(exc)}, status=exc.http_status)
    return exception_handler(exc, context)
