import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler


logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Единый формат ошибок:
    - DRF исключения: стандартный ответ DRF (400/401/403/404/...)
    - IntegrityError (БД): 400 с понятным сообщением (например, дубликат email)
    - Django ValidationError: 400
    - Прочее: 500 с {"detail": "Внутренняя ошибка сервера"}
    """
    response = exception_handler(exc, context)
    if response is not None:
        return response

    if isinstance(exc, IntegrityError):
        message = str(exc).lower()
        if "username" in message or "email" in message:
            return Response(
                {"email": ["Пользователь с таким email уже существует"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {"detail": "Нарушение целостности данных"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, DjangoValidationError):
        detail = getattr(exc, "message_dict", None) or {"detail": exc.messages}
        return Response(detail, status=status.HTTP_400_BAD_REQUEST)

    if isinstance(exc, Http404):
        return Response({"detail": "Не найдено"}, status=status.HTTP_404_NOT_FOUND)

    logger.exception("Unhandled exception", exc_info=exc)
    return Response(
        {"detail": "Внутренняя ошибка сервера"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
