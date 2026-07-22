from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AppSettingsAPIView,
    CalendarAPIView,
    FCMDeviceDetailAPIView,
    FCMDeviceListCreateAPIView,
    HelpCenterAPIView,
    LegalDocumentsAPIView,
    MatrixAPIView,
    MatrixBlockSettingsAPIView,
    PomodoroSessionAPIView,
    PomodoroSessionStateAPIView,
    PomodoroSettingsAPIView,
    ReminderAckAPIView,
    ReminderCompleteAPIView,
    ReminderSnoozeAPIView,
    RemindersDueAPIView,
    SoundCatalogAPIView,
    SettingsStubActionAPIView,
    TaskViewSet,
)

router = DefaultRouter()
router.register("tasks", TaskViewSet, basename="tasks")


urlpatterns = [
    path("", include(router.urls)),
    path("calendar/", CalendarAPIView.as_view(), name="calendar"),
    path("matrix/", MatrixAPIView.as_view(), name="matrix"),
    path("matrix/settings/", MatrixBlockSettingsAPIView.as_view(), name="matrix-settings"),
    path("reminders/due/", RemindersDueAPIView.as_view(), name="reminders-due"),
    path("reminders/<int:task_id>/ack/", ReminderAckAPIView.as_view(), name="reminders-ack"),
    path(
        "reminders/<int:task_id>/snooze/",
        ReminderSnoozeAPIView.as_view(),
        name="reminders-snooze",
    ),
    path(
        "reminders/<int:task_id>/complete/",
        ReminderCompleteAPIView.as_view(),
        name="reminders-complete",
    ),
    path("devices/", FCMDeviceListCreateAPIView.as_view(), name="fcm-devices"),
    path(
        "devices/<int:device_id>/",
        FCMDeviceDetailAPIView.as_view(),
        name="fcm-device-detail",
    ),
    path("sounds/", SoundCatalogAPIView.as_view(), name="sound-catalog"),
    path("pomodoro/settings/", PomodoroSettingsAPIView.as_view(), name="pomodoro-settings"),
    path("pomodoro/sessions/", PomodoroSessionAPIView.as_view(), name="pomodoro-sessions"),
    path(
        "pomodoro/sessions/<int:session_id>/state/",
        PomodoroSessionStateAPIView.as_view(),
        name="pomodoro-session-state",
    ),
    path("settings/", AppSettingsAPIView.as_view(), name="app-settings"),
    path("settings/stub-action/", SettingsStubActionAPIView.as_view(), name="settings-stub-action"),
    path("help/", HelpCenterAPIView.as_view(), name="help"),
    path("legal/documents/", LegalDocumentsAPIView.as_view(), name="legal-documents"),
]

