from django.conf import settings
from django.db import models


class Sound(models.Model):
    class Category(models.TextChoices):
        TIMER_END = "timer_end", "Звук завершения таймера"
        WORK_BACKGROUND = "work_background", "Фоновый звук"
        NOTIFICATION = "notification", "Звук уведомления"
        COMPLETION = "completion", "Звук завершения задачи"

    key = models.CharField("Ключ", max_length=50)
    category = models.CharField("Категория", max_length=30, choices=Category.choices)
    title = models.CharField("Название", max_length=120)
    emoji = models.CharField("Emoji", max_length=16, blank=True, default="")
    audio_file = models.FileField("Аудиофайл", upload_to="sounds/", blank=True, null=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        db_table = "planner_sound"
        verbose_name = "Аудиофайл"
        verbose_name_plural = "1. Аудио — все звуки"
        ordering = ("category", "sort_order", "key")
        constraints = [
            models.UniqueConstraint(fields=["key", "category"], name="uniq_sound_key_category"),
        ]

    def __str__(self) -> str:
        prefix = f"{self.emoji} " if self.emoji else ""
        return f"{prefix}{self.title} [{self.get_category_display()}]"


class PomodoroSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pomodoro_settings",
        verbose_name="Пользователь",
    )
    duration_minutes = models.PositiveIntegerField("Длительность таймера", default=30)
    short_break_minutes = models.PositiveIntegerField("Короткий перерыв", default=5)
    show_on_lock_screen = models.BooleanField("Показывать на экране блокировки", default=True)
    timer_end_sound = models.ForeignKey(
        Sound,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Звук завершения таймера",
        limit_choices_to={"category": Sound.Category.TIMER_END, "is_active": True},
    )
    work_sound = models.ForeignKey(
        Sound,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Фоновая мелодия",
        limit_choices_to={"category": Sound.Category.WORK_BACKGROUND, "is_active": True},
    )

    class Meta:
        db_table = "planner_pomodorosettings"
        verbose_name = "Настройки пользователя"
        verbose_name_plural = "2. Настройки пользователей"

    def __str__(self) -> str:
        return f"pomodoro::{self.user_id}"


class PomodoroSession(models.Model):
    class State(models.TextChoices):
        IDLE = "idle", "Ожидание"
        RUNNING = "running", "Запущен"
        PAUSED = "paused", "На паузе"
        STOPPED = "stopped", "Остановлен"
        COMPLETED = "completed", "Завершен"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pomodoro_sessions",
        verbose_name="Пользователь",
    )
    task = models.ForeignKey(
        "planner.Task",
        on_delete=models.SET_NULL,
        related_name="pomodoro_sessions",
        null=True,
        blank=True,
        verbose_name="Задача",
    )
    duration_minutes = models.PositiveIntegerField("Длительность", default=30)
    state = models.CharField("Состояние", max_length=20, choices=State.choices, default=State.IDLE)
    started_at = models.DateTimeField("Старт", blank=True, null=True)
    ended_at = models.DateTimeField("Окончание", blank=True, null=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        db_table = "planner_pomodorosession"
        verbose_name = "Сессия"
        verbose_name_plural = "3. Сессии"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"session::{self.id} ({self.state})"
