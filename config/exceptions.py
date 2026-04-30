from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Единый формат ошибок (DRF).
    Если DRF не обработал исключение — отдаём стандартное поведение.
    """
    response = exception_handler(exc, context)
    return response

