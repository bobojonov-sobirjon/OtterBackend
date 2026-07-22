from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@ottertime.ru",
)
class RegistrationEmailTests(TestCase):
    """Проверяет письмо после создания аккаунта."""

    def test_registration_sends_welcome_email(self):
        """Успешная регистрация отправляет одно welcome-письмо."""
        response = APIClient().post(
            "/api/v1/auth/register/",
            {
                "email": "welcome@example.com",
                "password": "Qx7!zP2@mN9#",
                "first_name": "Иван",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["welcome@example.com"])
        self.assertIn("ОТТЕР", mail.outbox[0].subject)
