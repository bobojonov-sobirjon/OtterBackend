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
    is_all_day = models.BooleanField(
        "Весь день (дата без времени)",
        default=False,
        help_text="True = задача с датой, но без конкретного времени (верхний блок календаря).",
    )
    reminder_at = models.DateTimeField("Напоминание", blank=True, null=True)
    reminder_offset_minutes = models.IntegerField(
        "Смещение напоминания (мин до срока)",
        blank=True,
        null=True,
        help_text="0 = в момент срока, 15 = за 15 минут. Клиент может сам считать reminder_at.",
    )
    reminder_delivered_at = models.DateTimeField(
        "Напоминание доставлено",
        blank=True,
        null=True,
        help_text="Когда клиент подтвердил показ уведомления.",
    )
    repeat_unit = models.CharField(
        "Единица повтора",
        max_length=10,
        choices=RepeatUnit.choices,
        default=RepeatUnit.NONE,
    )
    repeat_interval = models.PositiveIntegerField("Интервал повтора", default=1)
    repeat_until = models.DateField("Повторять до", blank=True, null=True)
    series_id = models.UUIDField(
        "ID серии повторов",
        blank=True,
        null=True,
        db_index=True,
        help_text="Общий идентификатор всех вхождений повторяющейся задачи.",
    )
    parent_task = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="child_occurrences",
        verbose_name="Предыдущее вхождение",
    )
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
            models.Index(fields=["user", "reminder_at"]),
            models.Index(fields=["user", "series_id"]),
        ]

    def __str__(self) -> str:
        return self.title

    def mark_completed(self, completed: bool) -> None:
        """Отмечает задачу выполненной или снимает отметку выполнения."""
        self.is_completed = completed
        self.completed_at = timezone.now() if completed else None


class TaskAttachment(models.Model):
    """Файлы, прикреплённые к задаче (несколько на одну задачу)."""

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="Задача",
    )
    file = models.FileField("Файл", upload_to="task_attachments/")
    original_name = models.CharField("Имя файла", max_length=255, blank=True, default="")
    content_type = models.CharField("MIME", max_length=120, blank=True, default="")
    size = models.PositiveIntegerField("Размер (байт)", default=0)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Вложение задачи"
        verbose_name_plural = "1b. Вложения задач"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.original_name or f"attachment::{self.pk}"


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
    date_filters = models.JSONField(
        "Фильтры по дате",
        default=list,
        blank=True,
        help_text="Список: overdue, today, tomorrow, later, no_deadline, with_deadline.",
    )
    date_filter = models.CharField(
        "Фильтр по дате",
        max_length=30,
        blank=True,
        default="",
        help_text="Legacy single value; use date_filters for multiple values.",
    )

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
    timezone = models.CharField(
        "Часовой пояс (IANA)",
        max_length=64,
        default="Europe/Moscow",
        help_text="Например Europe/Moscow, Asia/Tashkent. Влияет на группы и календарь.",
    )
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
    premium_until = models.DateTimeField("Премиум действует до", blank=True, null=True)

    class Meta:
        verbose_name = "Настройки приложения"
        verbose_name_plural = "3. Настройки приложения"

    def __str__(self) -> str:
        return f"settings::{self.user_id}"


class FCMDevice(models.Model):
    """FCM token устройства пользователя для push-уведомлений."""

    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        WEB = "web", "Web"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fcm_devices",
        verbose_name="Пользователь",
    )
    token = models.TextField("FCM token", unique=True)
    device_id = models.CharField("ID устройства", max_length=255)
    name = models.CharField("Название устройства", max_length=255, blank=True, default="")
    platform = models.CharField("Платформа", max_length=16, choices=Platform.choices)
    app_version = models.CharField("Версия приложения", max_length=50, blank=True, default="")
    is_active = models.BooleanField("Активно", default=True)
    last_seen_at = models.DateTimeField("Последняя активность", default=timezone.now)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Устройство FCM"
        verbose_name_plural = "3b. Устройства FCM"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "device_id"],
                name="unique_user_fcm_device",
            )
        ]
        ordering = ("-last_seen_at",)

    def __str__(self) -> str:
        return f"{self.user_id}::{self.platform}::{self.device_id}"


class UserNotification(models.Model):
    """In-app уведомления пользователя (центр уведомлений)."""

    class Type(models.TextChoices):
        TASK_REMINDER = "task_reminder", "Напоминание о задаче"
        SYSTEM = "system", "Системное"
        PREMIUM = "premium", "Премиум"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Пользователь",
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="user_notifications",
        verbose_name="Задача",
    )
    type = models.CharField(
        "Тип",
        max_length=32,
        choices=Type.choices,
        default=Type.TASK_REMINDER,
    )
    title = models.CharField("Заголовок", max_length=255)
    body = models.TextField("Текст", blank=True, default="")
    data = models.JSONField("Данные", default=dict, blank=True)
    is_read = models.BooleanField("Прочитано", default=False)
    read_at = models.DateTimeField("Прочитано в", blank=True, null=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Уведомление пользователя"
        verbose_name_plural = "3d. Уведомления пользователя"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "is_read", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}::{self.type}::{self.title}"


class NotificationDelivery(models.Model):
    """История отправки push-напоминания на конкретное устройство."""

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        SENT = "sent", "Отправлено"
        FAILED = "failed", "Ошибка"

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="notification_deliveries",
        verbose_name="Задача",
    )
    device = models.ForeignKey(
        FCMDevice,
        on_delete=models.CASCADE,
        related_name="notification_deliveries",
        verbose_name="Устройство",
    )
    status = models.CharField(
        "Статус",
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    message_id = models.CharField("FCM message ID", max_length=255, blank=True, default="")
    error = models.TextField("Ошибка", blank=True, default="")
    attempted_at = models.DateTimeField("Попытка отправки", blank=True, null=True)
    sent_at = models.DateTimeField("Отправлено", blank=True, null=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Доставка уведомления"
        verbose_name_plural = "3c. Доставка уведомлений"
        constraints = [
            models.UniqueConstraint(
                fields=["task", "device"],
                name="unique_task_device_notification",
            )
        ]
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.task_id}::{self.device_id}::{self.status}"


class FAQEntry(models.Model):
    """Вопрос и ответ для раздела FAQ мобильного приложения."""

    question = models.CharField("Вопрос", max_length=500)
    answer = models.TextField("Ответ")
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Вопрос FAQ"
        verbose_name_plural = "4a. FAQ"
        ordering = ("sort_order", "id")

    def __str__(self) -> str:
        return self.question


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
