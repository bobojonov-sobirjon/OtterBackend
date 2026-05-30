from django.contrib import admin

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


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "user", "priority", "is_completed", "due_at")
    list_filter = ("priority", "is_completed", "matrix_block")
    search_fields = ("title", "description", "user__email")


@admin.register(MatrixBlockSetting)
class MatrixBlockSettingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "block", "title")
    list_filter = ("block",)


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "language", "is_premium", "vibration_enabled")
    search_fields = ("user__email",)


@admin.register(PomodoroSettings)
class PomodoroSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "duration_minutes", "show_on_lock_screen")


@admin.register(PomodoroSession)
class PomodoroSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "task", "duration_minutes", "state", "created_at")
    list_filter = ("state",)


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

