from datetime import date, timedelta

from django.utils import timezone
from rest_framework import serializers

from .models import (
    AppSettings,
    HelpRequest,
    LegalDocument,
    MatrixBlockSetting,
    PremiumFeatureFlag,
    Task,
)
from apps.pomodoro.models import PomodoroSession, PomodoroSettings, Sound


def _sound_queryset(category: str):
    return Sound.objects.filter(category=category, is_active=True).order_by("sort_order", "key")


class SoundSerializer(serializers.ModelSerializer):
    audio_url = serializers.SerializerMethodField()

    class Meta:
        model = Sound
        fields = ("key", "category", "title", "emoji", "audio_url", "sort_order")
        read_only_fields = fields

    def get_audio_url(self, obj: Sound) -> str | None:
        if not obj.audio_file:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.audio_file.url)
        return obj.audio_file.url


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = (
            "id",
            "title",
            "description",
            "due_at",
            "start_at",
            "end_at",
            "reminder_at",
            "repeat_unit",
            "repeat_interval",
            "priority",
            "matrix_block",
            "image",
            "is_completed",
            "completed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("completed_at", "created_at", "updated_at")

    def validate(self, attrs):
        """Проверяет корректность времени начала и окончания задачи."""
        start_at = attrs.get("start_at", getattr(self.instance, "start_at", None))
        end_at = attrs.get("end_at", getattr(self.instance, "end_at", None))
        if start_at and end_at and end_at <= start_at:
            raise serializers.ValidationError({"end_at": "Время окончания должно быть позже времени начала."})
        return attrs

    def update(self, instance, validated_data):
        """Обновляет задачу и синхронизирует дату выполнения при отметке статуса."""
        is_completed = validated_data.get("is_completed")
        if is_completed is not None and is_completed != instance.is_completed:
            instance.mark_completed(is_completed)
        return super().update(instance, validated_data)


class TaskGroupSerializer(serializers.Serializer):
    key = serializers.CharField()
    title = serializers.CharField()
    count = serializers.IntegerField()
    tasks = TaskSerializer(many=True)


class MatrixBlockSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatrixBlockSetting
        fields = ("id", "block", "title", "allowed_priorities", "date_filter")


class AppSettingsSerializer(serializers.ModelSerializer):
    notification_sound = serializers.SlugRelatedField(
        slug_field="key",
        queryset=_sound_queryset(Sound.Category.NOTIFICATION),
    )
    completion_sound = serializers.SlugRelatedField(
        slug_field="key",
        queryset=_sound_queryset(Sound.Category.COMPLETION),
    )
    notification_sound_detail = SoundSerializer(source="notification_sound", read_only=True)
    completion_sound_detail = SoundSerializer(source="completion_sound", read_only=True)

    class Meta:
        model = AppSettings
        fields = (
            "language",
            "show_overdue",
            "show_today",
            "show_tomorrow",
            "show_later",
            "show_no_deadline",
            "show_completed",
            "bottom_tabs",
            "notification_sound",
            "notification_sound_detail",
            "completion_sound",
            "completion_sound_detail",
            "vibration_enabled",
            "is_premium",
            "premium_activated_at",
            "premium_until",
        )
        read_only_fields = (
            "is_premium",
            "premium_activated_at",
            "premium_until",
            "notification_sound_detail",
            "completion_sound_detail",
        )


class PomodoroSettingsSerializer(serializers.ModelSerializer):
    timer_end_sound = serializers.SlugRelatedField(
        slug_field="key",
        queryset=_sound_queryset(Sound.Category.TIMER_END),
    )
    work_sound = serializers.SlugRelatedField(
        slug_field="key",
        queryset=_sound_queryset(Sound.Category.WORK_BACKGROUND),
    )
    timer_end_sound_detail = SoundSerializer(source="timer_end_sound", read_only=True)
    work_sound_detail = SoundSerializer(source="work_sound", read_only=True)

    class Meta:
        model = PomodoroSettings
        fields = (
            "duration_minutes",
            "short_break_minutes",
            "show_on_lock_screen",
            "timer_end_sound",
            "timer_end_sound_detail",
            "work_sound",
            "work_sound_detail",
        )
        read_only_fields = ("timer_end_sound_detail", "work_sound_detail")

    def validate_short_break_minutes(self, value: int) -> int:
        if value not in {3, 5, 7, 10}:
            raise serializers.ValidationError("Допустимые значения: 3, 5, 7, 10.")
        return value

    def validate_duration_minutes(self, value: int) -> int:
        if value not in {15, 20, 25, 30, 45, 60}:
            raise serializers.ValidationError("Допустимые значения: 15, 20, 25, 30, 45, 60.")
        return value


class PomodoroSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PomodoroSession
        fields = ("id", "task", "duration_minutes", "state", "started_at", "ended_at", "created_at")
        read_only_fields = ("started_at", "ended_at", "created_at")


class PomodoroStateUpdateSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=PomodoroSession.State.choices)


class HelpRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = HelpRequest
        fields = ("id", "message", "screenshot", "created_at")
        read_only_fields = ("created_at",)


class PremiumFeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = PremiumFeatureFlag
        fields = ("key", "title", "is_premium", "is_enabled")


class LegalDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalDocument
        fields = ("doc_type", "title", "content", "updated_at")


def split_tasks_by_default_groups(tasks):
    """Разбивает задачи на группы списка по логике TZ."""
    now = timezone.localtime()
    today = now.date()
    tomorrow = today + timedelta(days=1)

    grouped = {
        "overdue": [],
        "today": [],
        "tomorrow": [],
        "later": [],
        "no_deadline": [],
        "completed": [],
    }

    for task in tasks:
        if task.is_completed:
            grouped["completed"].append(task)
            continue

        if not task.due_at:
            grouped["no_deadline"].append(task)
            continue

        due_date = timezone.localtime(task.due_at).date()
        if task.due_at < now:
            grouped["overdue"].append(task)
        elif due_date == today:
            grouped["today"].append(task)
        elif due_date == tomorrow:
            grouped["tomorrow"].append(task)
        else:
            grouped["later"].append(task)
    return grouped


def date_range_for_view(mode: str, selected_date: date):
    """Возвращает временной диапазон для режимов календаря: день/неделя/месяц/год."""
    if mode == "day":
        start = selected_date
        end = selected_date + timedelta(days=1)
    elif mode == "week":
        start = selected_date - timedelta(days=selected_date.weekday())
        end = start + timedelta(days=7)
    elif mode == "month":
        start = selected_date.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = next_month
    elif mode == "year":
        start = selected_date.replace(month=1, day=1)
        end = start.replace(year=start.year + 1)
    else:
        raise serializers.ValidationError({"view": "Поддерживаются только day/week/month/year."})
    return start, end

