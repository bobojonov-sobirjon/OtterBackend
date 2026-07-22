from datetime import date, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone
from rest_framework import serializers

from apps.pomodoro.models import PomodoroSession, PomodoroSettings, Sound

from .models import (
    AppSettings,
    FAQEntry,
    FCMDevice,
    HelpRequest,
    LegalDocument,
    MatrixBlockSetting,
    NotificationDelivery,
    PremiumFeatureFlag,
    Task,
    TaskAttachment,
)
from .services import complete_task_with_repeat, task_group_key


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


class TaskAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = TaskAttachment
        fields = (
            "id",
            "file",
            "file_url",
            "original_name",
            "content_type",
            "size",
            "created_at",
        )
        read_only_fields = ("original_name", "content_type", "size", "created_at", "file_url")

    def get_file_url(self, obj: TaskAttachment) -> str | None:
        if not obj.file:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url


class TaskSerializer(serializers.ModelSerializer):
    list_key = serializers.SerializerMethodField(
        help_text="Системный список: overdue|today|tomorrow|later|no_deadline|completed"
    )
    attachments = TaskAttachmentSerializer(many=True, read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = (
            "id",
            "title",
            "description",
            "due_at",
            "start_at",
            "end_at",
            "is_all_day",
            "reminder_at",
            "reminder_offset_minutes",
            "reminder_delivered_at",
            "repeat_unit",
            "repeat_interval",
            "repeat_until",
            "series_id",
            "parent_task",
            "priority",
            "matrix_block",
            "image",
            "image_url",
            "attachments",
            "is_completed",
            "completed_at",
            "list_key",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "completed_at",
            "created_at",
            "updated_at",
            "series_id",
            "parent_task",
            "reminder_delivered_at",
            "list_key",
            "attachments",
            "image_url",
        )

    def get_list_key(self, obj: Task) -> str:
        now = self.context.get("now") or timezone.localtime()
        return task_group_key(obj, now=now)

    def get_image_url(self, obj: Task) -> str | None:
        if not obj.image:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url

    def validate_reminder_offset_minutes(self, value):
        """Разрешает reminder от 0 минут до 30 дней до срока."""
        if value is not None and not 0 <= value <= 30 * 24 * 60:
            raise serializers.ValidationError("Допустимо от 0 до 43200 минут.")
        return value

    def validate(self, attrs):
        start_at = attrs.get("start_at", getattr(self.instance, "start_at", None))
        end_at = attrs.get("end_at", getattr(self.instance, "end_at", None))
        if start_at and end_at and end_at <= start_at:
            raise serializers.ValidationError(
                {"end_at": "Время окончания должно быть позже времени начала."}
            )
        repeat_unit = attrs.get("repeat_unit", getattr(self.instance, "repeat_unit", Task.RepeatUnit.NONE))
        repeat_interval = attrs.get(
            "repeat_interval", getattr(self.instance, "repeat_interval", 1)
        )
        if repeat_unit != Task.RepeatUnit.NONE and int(repeat_interval or 0) < 1:
            raise serializers.ValidationError(
                {"repeat_interval": "Интервал повтора должен быть >= 1."}
            )
        if "reminder_offset_minutes" in attrs and "reminder_at" not in attrs:
            offset = attrs.get("reminder_offset_minutes")
            if offset is not None:
                anchor = attrs.get(
                    "due_at",
                    getattr(self.instance, "due_at", None),
                ) or attrs.get(
                    "start_at",
                    getattr(self.instance, "start_at", None),
                )
                if not anchor:
                    raise serializers.ValidationError(
                        {
                            "reminder_offset_minutes": (
                                "Для смещения напоминания укажите due_at или start_at."
                            )
                        }
                    )
                attrs["reminder_at"] = anchor - timedelta(minutes=offset)
        return attrs

    def create(self, validated_data):
        import uuid

        if (
            validated_data.get("repeat_unit", Task.RepeatUnit.NONE) != Task.RepeatUnit.NONE
            and not validated_data.get("series_id")
        ):
            validated_data["series_id"] = uuid.uuid4()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        was_completed = instance.is_completed
        is_completed = validated_data.pop("is_completed", None)
        # Changing reminder_at resets delivery flag
        if "reminder_at" in validated_data and validated_data["reminder_at"] != instance.reminder_at:
            validated_data["reminder_delivered_at"] = None
        if (
            validated_data.get("repeat_unit", instance.repeat_unit) != Task.RepeatUnit.NONE
            and not instance.series_id
            and "series_id" not in validated_data
        ):
            import uuid

            validated_data["series_id"] = uuid.uuid4()
        instance = super().update(instance, validated_data)
        if is_completed is True and not was_completed:
            instance, _ = complete_task_with_repeat(instance)
        elif is_completed is False and was_completed:
            instance.mark_completed(False)
            instance.save(update_fields=["is_completed", "completed_at", "updated_at"])
        return instance


class TaskGroupSerializer(serializers.Serializer):
    key = serializers.CharField()
    title = serializers.CharField()
    count = serializers.IntegerField()
    tasks = TaskSerializer(many=True)


class MatrixBlockSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatrixBlockSetting
        fields = (
            "id",
            "block",
            "title",
            "allowed_priorities",
            "date_filters",
            "date_filter",
        )

    def validate_date_filter(self, value: str) -> str:
        allowed = {
            "",
            "any",
            "all",
            "overdue",
            "today",
            "tomorrow",
            "later",
            "no_deadline",
            "no_date",
            "with_deadline",
            "with_date",
        }
        v = (value or "").strip().lower()
        if v not in allowed:
            raise serializers.ValidationError(
                "Допустимо: any, overdue, today, tomorrow, later, no_deadline, with_deadline."
            )
        return v

    def validate_date_filters(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Ожидается список фильтров по дате.")
        allowed = {
            "any",
            "all",
            "overdue",
            "today",
            "tomorrow",
            "later",
            "no_deadline",
            "no_date",
            "with_deadline",
            "with_date",
        }
        normalized = [str(item).strip().lower() for item in value]
        bad = [item for item in normalized if item not in allowed]
        if bad:
            raise serializers.ValidationError(f"Неизвестные фильтры: {bad}")
        return list(dict.fromkeys(normalized))

    def validate_allowed_priorities(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Ожидается список приоритетов.")
        valid = {c.value for c in Task.Priority}
        bad = [p for p in value if p not in valid]
        if bad:
            raise serializers.ValidationError(f"Неизвестные приоритеты: {bad}")
        return value


class FCMDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMDevice
        fields = (
            "id",
            "token",
            "device_id",
            "name",
            "platform",
            "app_version",
            "is_active",
            "last_seen_at",
            "created_at",
        )
        read_only_fields = ("id", "last_seen_at", "created_at")
        extra_kwargs = {"token": {"write_only": True, "validators": []}}


class NotificationDeliverySerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source="device.name", read_only=True)

    class Meta:
        model = NotificationDelivery
        fields = (
            "id",
            "task",
            "device",
            "device_name",
            "status",
            "message_id",
            "error",
            "attempted_at",
            "sent_at",
            "created_at",
        )
        read_only_fields = fields


class ReminderSnoozeSerializer(serializers.Serializer):
    minutes = serializers.IntegerField(min_value=1, max_value=1440, default=10)


class FAQEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQEntry
        fields = ("id", "question", "answer", "sort_order", "updated_at")
        read_only_fields = fields


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
            "timezone",
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

    def validate_timezone(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            return "Europe/Moscow"
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise serializers.ValidationError(
                "Некорректный IANA timezone. Пример: Europe/Moscow, Asia/Tashkent."
            ) from exc
        return value


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


def split_tasks_by_default_groups(tasks, *, now=None):
    """Разбивает задачи на группы списка по логике TZ."""
    if now is None:
        now = timezone.localtime()

    grouped = {
        "overdue": [],
        "today": [],
        "tomorrow": [],
        "later": [],
        "no_deadline": [],
        "completed": [],
    }

    for task in tasks:
        key = task_group_key(task, now=now)
        grouped[key].append(task)
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
