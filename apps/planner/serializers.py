from datetime import date, timedelta

from django.utils import timezone
from rest_framework import serializers

from .models import (
    AppSettings,
    HelpRequest,
    LegalDocument,
    MatrixBlockSetting,
    PomodoroSession,
    PomodoroSettings,
    PremiumFeatureFlag,
    Task,
)


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
            "completion_sound",
            "vibration_enabled",
            "is_premium",
            "premium_activated_at",
        )
        read_only_fields = ("is_premium", "premium_activated_at")


class PomodoroSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PomodoroSettings
        fields = ("duration_minutes", "show_on_lock_screen", "timer_end_sound", "work_sound")


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


class PremiumCheckoutSerializer(serializers.Serializer):
    tariff = serializers.CharField(required=False, default="monthly")


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

