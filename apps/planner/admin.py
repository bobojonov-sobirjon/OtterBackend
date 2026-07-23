from django.contrib import admin

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
    UserNotification,
)


class TaskAttachmentInline(admin.TabularInline):
    model = TaskAttachment
    extra = 0
    readonly_fields = ("created_at", "size", "content_type")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "user",
        "priority",
        "is_completed",
        "is_all_day",
        "due_at",
        "repeat_unit",
    )
    list_filter = ("priority", "is_completed", "matrix_block", "is_all_day", "repeat_unit")
    search_fields = ("title", "description", "user__email", "series_id")
    inlines = [TaskAttachmentInline]


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "original_name", "size", "created_at")
    search_fields = ("original_name", "task__title", "task__user__email")


@admin.register(MatrixBlockSetting)
class MatrixBlockSettingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "block", "title", "date_filter")
    list_filter = ("block", "date_filter")


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "language",
        "timezone",
        "notification_sound",
        "completion_sound",
        "is_premium",
        "premium_until",
    )
    search_fields = ("user__email",)
    autocomplete_fields = ("notification_sound", "completion_sound")


@admin.register(FCMDevice)
class FCMDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "name",
        "platform",
        "app_version",
        "is_active",
        "last_seen_at",
    )
    list_filter = ("platform", "is_active")
    search_fields = ("user__email", "device_id", "name")
    readonly_fields = ("token", "created_at", "updated_at", "last_seen_at")


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "type",
        "title",
        "is_read",
        "task",
        "created_at",
    )
    list_filter = ("type", "is_read")
    search_fields = ("user__email", "title", "body")
    readonly_fields = ("created_at", "read_at")


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "device", "status", "attempted_at", "sent_at")
    list_filter = ("status", "device__platform")
    search_fields = ("task__title", "task__user__email", "message_id", "error")
    readonly_fields = (
        "task",
        "device",
        "status",
        "message_id",
        "error",
        "attempted_at",
        "sent_at",
        "created_at",
    )


@admin.register(FAQEntry)
class FAQEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "sort_order", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("question", "answer")
    list_editable = ("sort_order", "is_active")


@admin.register(HelpRequest)
class HelpRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at")
    search_fields = ("user__email", "message")


@admin.register(PremiumFeatureFlag)
class PremiumFeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "is_premium", "is_enabled")
    list_filter = ("is_premium", "is_enabled")


@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display = ("doc_type", "title", "updated_at")
