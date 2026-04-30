import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("Email обязателен")
        email = self.normalize_email(email)
        user = self.model(email=email, username=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email=email, password=password, **extra_fields)

    def create_superuser(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email=email, password=password, **extra_fields)


class CustomUser(AbstractUser):
    username = models.CharField("Логин", max_length=150, unique=True)
    email = models.EmailField("Email", unique=True)

    first_name = models.CharField("Имя", max_length=150, blank=True, null=True)
    last_name = models.CharField("Фамилия", max_length=150, blank=True, null=True)

    avatar = models.ImageField("Аватар", upload_to="avatars/", blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = CustomUserManager()

    def __str__(self) -> str:
        return self.email


class PasswordResetRequest(models.Model):
    """
    Запрос на сброс пароля через email-код.
    1) отправили код
    2) проверили код -> выдаём reset_token
    3) по reset_token меняем пароль
    """

    user = models.ForeignKey(
        CustomUser,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="password_reset_requests",
    )
    email = models.EmailField("Email", blank=True, null=True)
    code = models.CharField("Код", max_length=10, blank=True, null=True)
    reset_token = models.UUIDField("Токен сброса", default=uuid.uuid4, unique=True)
    expires_at = models.DateTimeField("Срок действия", blank=True, null=True)
    used_at = models.DateTimeField("Использован", blank=True, null=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Сброс пароля"
        verbose_name_plural = "Сбросы пароля"
        indexes = [
            models.Index(fields=["email", "code"]),
            models.Index(fields=["reset_token"]),
        ]

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

