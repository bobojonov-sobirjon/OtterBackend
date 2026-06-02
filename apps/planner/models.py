from django.conf import settings
from django.db import models
from django.utils import timezone

class Task(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Низкий"
        MEDIUM = "medium", "Средний"
        HIGH = "high", "Высокий"
        CRITICAL = "critical", "Критичный"

    class MatrixBlock(models.TextChoices):
        URGENT_IMPORTANT = "urgent_important", "Срочно и важно"
        NOT_URGENT_IMPORTANT = "not_urgent_important", "Не срочно и важно"
        URGENT_NOT_IMPORTANT = "urgent_not_important", "Срочно и не важно"
        NOT_URGENT_NOT_IMPORTANT = "not_urgent_not_important", "Не срочно и не важно"

    class RepeatUnit(models.TextChoices):
        NONE = "none", "Без повтора"
        DAY = "day", "День"
        WEEK = "week", "Неделя"
        MONTH = "month", "Месяц"
        YEAR = "year", "Год"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name="Пользователь",
    )
    title = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", blank=True, null=True)
    due_at = models.DateTimeField("Срок выполнения", blank=True, null=True)
    start_at = models.DateTimeField("Начало", blank=True, null=True)
    end_at = models.DateTimeField("Окончание", blank=True, null=True)
    reminder_at = models.DateTimeField("Напоминание", blank=True, null=True)
    repeat_unit = models.CharField(
        "Единица повтора",
        max_length=10,
        choices=RepeatUnit.choices,
        default=RepeatUnit.NONE,
    )
    repeat_interval = models.PositiveIntegerField("Интервал повтора", default=1)
    priority = models.CharField(
        "Приоритет",
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    matrix_block = models.CharField(
        "Блок матрицы Эйзенхауэра",
        max_length=30,
        choices=MatrixBlock.choices,
        default=MatrixBlock.NOT_URGENT_IMPORTANT,
    )
    image = models.ImageField("Изображение", upload_to="task_images/", blank=True, null=True)
    is_completed = models.BooleanField("Выполнено", default=False)
    completed_at = models.DateTimeField("Выполнено в", blank=True, null=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "1. Задачи"
        ordering = ("is_completed", "due_at", "-created_at")
        indexes = [
            models.Index(fields=["user", "due_at"]),
            models.Index(fields=["user", "is_completed"]),
            models.Index(fields=["user", "matrix_block"]),
        ]

    def __str__(self) -> str:
        return self.title

    def mark_completed(self, completed: bool) -> None:
        """Отмечает задачу выполненной или снимает отметку выполнения."""
        self.is_completed = completed
        self.completed_at = timezone.now() if completed else None


class MatrixBlockSetting(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="matrix_block_settings",
        verbose_name="Пользователь",
    )
    block = models.CharField("Блок", max_length=30, choices=Task.MatrixBlock.choices)
    title = models.CharField("Название блока", max_length=100)
    allowed_priorities = models.JSONField("Разрешенные приоритеты", default=list, blank=True)
    date_filter = models.CharField("Фильтр по дате", max_length=30, blank=True, default="")

    class Meta:
        verbose_name = "Настройка блока Эйзенхауэра"
        verbose_name_plural = "2. Матрица — блоки"
        unique_together = ("user", "block")

    def __str__(self) -> str:
        return f"{self.user_id}::{self.block}"


class AppSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="app_settings",
        verbose_name="Пользователь",
    )
    language = models.CharField("Язык", max_length=10, default="ru")
    show_overdue = models.BooleanField("Показывать просрочено", default=True)
    show_today = models.BooleanField("Показывать сегодня", default=True)
    show_tomorrow = models.BooleanField("Показывать завтра", default=True)
    show_later = models.BooleanField("Показывать позже", default=True)
    show_no_deadline = models.BooleanField("Показывать без срока", default=True)
    show_completed = models.BooleanField("Показывать выполнено", default=True)
    bottom_tabs = models.JSONField(
        "Вкладки нижнего меню",
        default=list,
        blank=True,
        help_text="Порядок вкладок в нижнем меню.",
    )
    notification_sound = models.ForeignKey(
        "pomodoro.Sound",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Звук уведомления",
        limit_choices_to={"category": "notification", "is_active": True},
    )
    completion_sound = models.ForeignKey(
        "pomodoro.Sound",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Звук завершения",
        limit_choices_to={"category": "completion", "is_active": True},
    )
    vibration_enabled = models.BooleanField("Вибрация", default=True)
    is_premium = models.BooleanField("Премиум", default=False)
    premium_activated_at = models.DateTimeField("Дата активации премиум", blank=True, null=True)

    class Meta:
        verbose_name = "Настройки приложения"
        verbose_name_plural = "3. Настройки приложения"

    def __str__(self) -> str:
        return f"settings::{self.user_id}"


class HelpRequest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="help_requests",
        verbose_name="Пользователь",
    )
    message = models.TextField("Сообщение")
    screenshot = models.ImageField("Скриншот", upload_to="help_requests/", blank=True, null=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Запрос в поддержку"
        verbose_name_plural = "4. Запросы в поддержку"
        ordering = ("-created_at",)


class PremiumFeatureFlag(models.Model):
    key = models.CharField("Ключ функции", max_length=80, unique=True)
    title = models.CharField("Название", max_length=150)
    is_premium = models.BooleanField("Премиум функция", default=False)
    is_enabled = models.BooleanField("Включена", default=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Флаг премиум функции"
        verbose_name_plural = "5. Премиум — функции"
        ordering = ("key",)

    def __str__(self) -> str:
        return self.key


class LegalDocument(models.Model):
    class DocType(models.TextChoices):
        OFFER = "offer", "Публичная оферта"
        PRIVACY = "privacy", "Политика конфиденциальности"
        REFUND = "refund", "Политика возвратов"
        PERSONAL_DATA = "personal_data", "Согласие на обработку ПДн"

    doc_type = models.CharField("Тип документа", max_length=30, choices=DocType.choices, unique=True)
    title = models.CharField("Название", max_length=200)
    content = models.TextField("Содержимое")
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Юридический документ"
        verbose_name_plural = "6. Юридические документы"
        ordering = ("doc_type",)

    def __str__(self) -> str:
        return self.title

