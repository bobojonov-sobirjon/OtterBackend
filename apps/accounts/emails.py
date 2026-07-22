"""Служебные email-письма аккаунта."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_welcome_email(user) -> bool:
    """Отправляет письмо об успешном создании аккаунта без срыва регистрации."""
    if not getattr(user, "email", ""):
        return False
    try:
        html = render_to_string("emails/welcome.html", {"user": user})
        send_mail(
            subject="Добро пожаловать в ОТТЕР",
            message=(
                "Ваш аккаунт ОТТЕР успешно создан. "
                "Теперь вы можете планировать задачи, календарь и фокус-сессии."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html,
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception("Welcome email failed user=%s", getattr(user, "id", None))
        return False
