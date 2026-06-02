from django.contrib import admin
from django.utils.html import format_html

from .models import PomodoroSession, PomodoroSettings, Sound


@admin.register(Sound)
class SoundAdmin(admin.ModelAdmin):
    list_display = ("emoji", "title", "key", "category", "sort_order", "is_active", "has_audio", "play_link")
    list_filter = ("category", "is_active")
    list_editable = ("sort_order", "is_active")
    search_fields = ("key", "title")
    ordering = ("category", "sort_order", "key")
    fieldsets = (
        (None, {"fields": ("category", "key", "title", "emoji", "sort_order", "is_active")}),
        (
            "Аудиофайл",
            {
                "fields": ("audio_file",),
                "description": "Загрузите mp3/wav — файл сразу доступен в API GET /api/v1/sounds/",
            },
        ),
    )

    @admin.display(boolean=True, description="Файл")
    def has_audio(self, obj: Sound) -> bool:
        return bool(obj.audio_file)

    @admin.display(description="▶")
    def play_link(self, obj: Sound) -> str:
        if not obj.audio_file:
            return "—"
        return format_html('<a href="{}" target="_blank">play</a>', obj.audio_file.url)


@admin.register(PomodoroSettings)
class PomodoroSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "duration_minutes", "short_break_minutes", "timer_end_sound", "work_sound")
    search_fields = ("user__email",)
    autocomplete_fields = ("timer_end_sound", "work_sound")
    fieldsets = (
        (None, {"fields": ("user", "duration_minutes", "short_break_minutes", "show_on_lock_screen")}),
        ("Звуки пользователя", {"fields": ("timer_end_sound", "work_sound")}),
    )


@admin.register(PomodoroSession)
class PomodoroSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "task", "duration_minutes", "state", "created_at")
    list_filter = ("state",)
    search_fields = ("user__email",)
