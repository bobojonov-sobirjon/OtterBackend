from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AppSettingsAPIView,
    CalendarAPIView,
    HelpCenterAPIView,
    LegalDocumentsAPIView,
    MatrixAPIView,
    MatrixBlockSettingsAPIView,
    PomodoroSessionAPIView,
    PomodoroSessionStateAPIView,
    PomodoroSettingsAPIView,
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
    path("sounds/", SoundCatalogAPIView.as_view(), name="sound-catalog"),
    path("pomodoro/settings/", PomodoroSettingsAPIView.as_view(), name="pomodoro-settings"),
    path("pomodoro/sessions/", PomodoroSessionAPIView.as_view(), name="pomodoro-sessions"),
    path("pomodoro/sessions/<int:session_id>/state/", PomodoroSessionStateAPIView.as_view(), name="pomodoro-session-state"),
    path("settings/", AppSettingsAPIView.as_view(), name="app-settings"),
    path("settings/stub-action/", SettingsStubActionAPIView.as_view(), name="settings-stub-action"),
    path("help/", HelpCenterAPIView.as_view(), name="help"),
    path("legal/documents/", LegalDocumentsAPIView.as_view(), name="legal-documents"),
]

