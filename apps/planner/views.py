from datetime import datetime

from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.pomodoro.models import PomodoroSession, PomodoroSettings, Sound

from .models import (
    AppSettings,
    FAQEntry,
    FCMDevice,
    LegalDocument,
    MatrixBlockSetting,
    Task,
    TaskAttachment,
    UserNotification,
)
from .serializers import (
    AppSettingsSerializer,
    FAQEntrySerializer,
    FCMDeviceSerializer,
    HelpRequestSerializer,
    LegalDocumentSerializer,
    MatrixBlockSettingSerializer,
    PomodoroSessionSerializer,
    PomodoroSettingsSerializer,
    PomodoroStateUpdateSerializer,
    ReminderSnoozeSerializer,
    SoundSerializer,
    TaskAttachmentSerializer,
    TaskSerializer,
    UserNotificationSerializer,
    date_range_for_view,
    split_tasks_by_default_groups,
)
from .services import (
    ack_reminder,
    activate_user_timezone,
    apply_matrix_filters,
    calendar_task_queryset,
    complete_task_with_repeat,
    delete_task,
    pending_reminders_queryset,
    reassign_matrix_tasks,
    snooze_reminder,
    split_calendar_tasks,
)


def _default_sound(key: str, category: str) -> Sound | None:
    return Sound.objects.filter(key=key, category=category, is_active=True).first()


def get_or_create_user_settings(user):
    """Создает дефолтные настройки приложения, если их еще нет у пользователя."""
    settings_obj, _ = AppSettings.objects.get_or_create(
        user=user,
        defaults={
            "bottom_tabs": ["tasks", "calendar", "matrix", "pomodoro", "settings"],
            "timezone": "Europe/Moscow",
            "notification_sound": _default_sound("default", Sound.Category.NOTIFICATION),
            "completion_sound": _default_sound("default", Sound.Category.COMPLETION),
        },
    )
    return settings_obj


def get_or_create_pomodoro_settings(user):
    """Создает дефолтные настройки помодоро, если пользователь их еще не настраивал."""
    settings_obj, _ = PomodoroSettings.objects.get_or_create(
        user=user,
        defaults={
            "timer_end_sound": _default_sound("bell", Sound.Category.TIMER_END),
            "work_sound": _default_sound("none", Sound.Category.WORK_BACKGROUND),
        },
    )
    return settings_obj


def ensure_default_matrix_settings(user):
    """Гарантирует наличие настроек всех 4 блоков матрицы Эйзенхауэра."""
    defaults = [
        (Task.MatrixBlock.URGENT_IMPORTANT, "Срочно и важно"),
        (Task.MatrixBlock.NOT_URGENT_IMPORTANT, "Не срочно и важно"),
        (Task.MatrixBlock.URGENT_NOT_IMPORTANT, "Срочно и не важно"),
        (Task.MatrixBlock.NOT_URGENT_NOT_IMPORTANT, "Не срочно и не важно"),
    ]
    for block, title in defaults:
        MatrixBlockSetting.objects.get_or_create(
            user=user,
            block=block,
            defaults={
                "title": title,
                "allowed_priorities": [],
                "date_filters": [],
                "date_filter": "",
            },
        )


@extend_schema_view(
    list=extend_schema(
        tags=["Задачи"],
        summary="Список задач",
        description=(
            "Возвращает список задач текущего пользователя. "
            "Фильтры: `search`, `is_completed`, `matrix_block`. "
            "В каждой задаче есть `list_key` (overdue/today/…) — для открытия из поиска."
        ),
    ),
    retrieve=extend_schema(tags=["Задачи"], summary="Детальная информация по задаче"),
    create=extend_schema(
        tags=["Задачи"],
        summary="Создание задачи",
        description=(
            "Создаёт задачу. `is_all_day=true` — дата без времени (верхний блок календаря). "
            "Повтор: `repeat_unit` + `repeat_interval`. Вложения — отдельным API."
        ),
    ),
    update=extend_schema(tags=["Задачи"], summary="Полное обновление задачи"),
    partial_update=extend_schema(tags=["Задачи"], summary="Частичное обновление задачи"),
    destroy=extend_schema(
        tags=["Задачи"],
        summary="Удаление задачи",
        description=(
            "По умолчанию удаляет только это вхождение. "
            "Для серии: `?scope=series` или body `{\"scope\": \"series\"}`."
        ),
        parameters=[
            OpenApiParameter(
                name="scope",
                type=str,
                required=False,
                description="this (default) | series",
            ),
        ],
    ),
)
class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.user and request.user.is_authenticated:
            activate_user_timezone(request.user)

    def get_queryset(self):
        queryset = (
            Task.objects.filter(user=self.request.user)
            .prefetch_related(
                Prefetch("attachments", queryset=TaskAttachment.objects.order_by("-created_at"))
            )
            .order_by("is_completed", "due_at", "-created_at")
        )
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )
        is_completed = self.request.query_params.get("is_completed")
        if is_completed in {"true", "false"}:
            queryset = queryset.filter(is_completed=(is_completed == "true"))
        matrix_block = self.request.query_params.get("matrix_block")
        if matrix_block:
            queryset = queryset.filter(matrix_block=matrix_block)
        return queryset

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["now"] = timezone.localtime()
        return ctx

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        reassign_matrix_tasks(self.request.user)

    def perform_update(self, serializer):
        serializer.save()
        reassign_matrix_tasks(self.request.user)

    def destroy(self, request, *args, **kwargs):
        task = self.get_object()
        scope = request.query_params.get("scope") or request.data.get("scope") or "this"
        if scope not in {"this", "series"}:
            return Response(
                {"scope": ["Допустимо: this | series."]},
                status=400,
            )
        result = delete_task(task, scope=scope)
        return Response(result, status=200)

    @extend_schema(
        tags=["Задачи"],
        summary="Группировка задач по системным спискам",
        description=(
            "Группы: `Просрочено`, `Сегодня`, `Завтра`, `Позже`, `Без срока`, `Выполнено`. "
            "Учитывает timezone пользователя из настроек."
        ),
    )
    @action(detail=False, methods=["get"], url_path="grouped")
    def grouped(self, request):
        activate_user_timezone(request.user)
        now = timezone.localtime()
        tasks = list(
            Task.objects.filter(user=request.user).prefetch_related("attachments")
        )
        grouped = split_tasks_by_default_groups(tasks, now=now)
        settings_obj = get_or_create_user_settings(request.user)
        visibility = {
            "overdue": settings_obj.show_overdue,
            "today": settings_obj.show_today,
            "tomorrow": settings_obj.show_tomorrow,
            "later": settings_obj.show_later,
            "no_deadline": settings_obj.show_no_deadline,
            "completed": settings_obj.show_completed,
        }
        titles = {
            "overdue": "Просрочено",
            "today": "Сегодня",
            "tomorrow": "Завтра",
            "later": "Позже",
            "no_deadline": "Без срока",
            "completed": "Выполнено",
        }
        data = []
        for key, items in grouped.items():
            if not visibility.get(key, True):
                continue
            data.append(
                {
                    "key": key,
                    "title": titles[key],
                    "count": len(items),
                    "tasks": TaskSerializer(
                        items, many=True, context={"request": request, "now": now}
                    ).data,
                }
            )
        return Response(data, status=200)

    @extend_schema(
        tags=["Задачи"],
        summary="Отметить задачу выполненной",
        description=(
            "Ставит статус выполнено. Если задан повтор (`repeat_unit` ≠ none), "
            "автоматически создаётся следующее вхождение. "
            "Ответ: `{ task, next_task }`."
        ),
    )
    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        task = self.get_object()
        completed, next_task = complete_task_with_repeat(task)
        ctx = {"request": request, "now": timezone.localtime()}
        # Backward-compatible: task fields at root + optional next_task
        payload = TaskSerializer(completed, context=ctx).data
        payload["next_task"] = (
            TaskSerializer(next_task, context=ctx).data if next_task else None
        )
        return Response(payload, status=200)

    @extend_schema(tags=["Задачи"], summary="Снять отметку выполнения")
    @action(detail=True, methods=["post"], url_path="uncomplete")
    def uncomplete(self, request, pk=None):
        task = self.get_object()
        task.mark_completed(False)
        task.save(update_fields=["is_completed", "completed_at", "updated_at"])
        return Response(
            TaskSerializer(task, context={"request": request, "now": timezone.localtime()}).data,
            status=200,
        )

    @extend_schema(
        tags=["Задачи / Вложения"],
        summary="Список вложений задачи",
        responses={200: TaskAttachmentSerializer(many=True)},
    )
    @action(detail=True, methods=["get", "post"], url_path="attachments")
    def attachments(self, request, pk=None):
        task = self.get_object()
        if request.method.lower() == "get":
            qs = task.attachments.all()
            return Response(
                TaskAttachmentSerializer(qs, many=True, context={"request": request}).data,
                status=200,
            )

        upload = request.FILES.get("file") or request.FILES.get("attachment")
        if not upload:
            return Response({"file": ["Файл обязателен (multipart field: file)."]}, status=400)
        att = TaskAttachment.objects.create(
            task=task,
            file=upload,
            original_name=getattr(upload, "name", "") or "",
            content_type=getattr(upload, "content_type", "") or "",
            size=int(getattr(upload, "size", 0) or 0),
        )
        return Response(
            TaskAttachmentSerializer(att, context={"request": request}).data,
            status=201,
        )

    @extend_schema(tags=["Задачи / Вложения"], summary="Удалить вложение")
    @action(
        detail=True,
        methods=["delete"],
        url_path=r"attachments/(?P<attachment_id>[^/.]+)",
    )
    def delete_attachment(self, request, pk=None, attachment_id=None):
        task = self.get_object()
        att = get_object_or_404(TaskAttachment, id=attachment_id, task=task)
        if att.file:
            att.file.delete(save=False)
        att.delete()
        return Response(status=204)


class CalendarAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Календарь"],
        summary="Задачи для календарного представления",
        description=(
            "Возвращает задачи в диапазоне `day|week|month|year`. "
            "Разделяет `all_day_tasks` (дата без времени) и `timed_tasks`. "
            "Задачи БЕЗ даты не попадают в календарь."
        ),
        parameters=[
            OpenApiParameter(name="view", type=str, required=True, description="day|week|month|year"),
            OpenApiParameter(name="date", type=str, required=True, description="YYYY-MM-DD"),
        ],
    )
    def get(self, request):
        activate_user_timezone(request.user)
        view_mode = request.query_params.get("view", "day")
        date_str = request.query_params.get("date")
        if not date_str:
            return Response({"date": ["Параметр date обязателен."]}, status=400)

        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"date": ["Используйте формат YYYY-MM-DD."]}, status=400)

        start, end = date_range_for_view(view_mode, selected_date)
        start_dt = timezone.make_aware(datetime.combine(start, datetime.min.time()))
        end_dt = timezone.make_aware(datetime.combine(end, datetime.min.time()))

        tasks = list(
            calendar_task_queryset(request.user, start_dt, end_dt).prefetch_related("attachments")
        )
        all_day, timed = split_calendar_tasks(tasks)
        ctx = {"request": request, "now": timezone.localtime()}
        return Response(
            {
                "view": view_mode,
                "date": date_str,
                "range_start": start.isoformat(),
                "range_end": end.isoformat(),
                "timezone": str(timezone.get_current_timezone()),
                "all_day_tasks": TaskSerializer(all_day, many=True, context=ctx).data,
                "timed_tasks": TaskSerializer(timed, many=True, context=ctx).data,
                # backwards-compatible flat list
                "tasks": TaskSerializer(tasks, many=True, context=ctx).data,
            },
            status=200,
        )


class MatrixAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Матрица Эйзенхауэра"],
        summary="Получить блоки матрицы с задачами",
        description=(
            "Возвращает 4 блока. Фильтры `allowed_priorities` и `date_filter` "
            "из настроек блока применяются на сервере."
        ),
    )
    def get(self, request):
        activate_user_timezone(request.user)
        ensure_default_matrix_settings(request.user)
        reassign_matrix_tasks(request.user)
        now = timezone.localtime()
        settings_qs = MatrixBlockSetting.objects.filter(user=request.user).order_by("id")
        base_tasks = Task.objects.filter(user=request.user, is_completed=False)

        payload = []
        for block_setting in settings_qs:
            block_tasks = base_tasks.filter(matrix_block=block_setting.block)
            block_tasks = apply_matrix_filters(block_tasks, block_setting, now=now)
            block_tasks = block_tasks.prefetch_related("attachments")
            payload.append(
                {
                    "block": block_setting.block,
                    "title": block_setting.title,
                    "allowed_priorities": block_setting.allowed_priorities,
                    "date_filters": block_setting.date_filters,
                    "date_filter": block_setting.date_filter,
                    "count": block_tasks.count(),
                    "tasks": TaskSerializer(
                        block_tasks, many=True, context={"request": request, "now": now}
                    ).data,
                }
            )
        return Response(payload, status=200)


class MatrixBlockSettingsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Матрица Эйзенхауэра"], summary="Получить настройки блоков матрицы")
    def get(self, request):
        ensure_default_matrix_settings(request.user)
        items = MatrixBlockSetting.objects.filter(user=request.user).order_by("id")
        return Response(MatrixBlockSettingSerializer(items, many=True).data, status=200)

    @extend_schema(
        tags=["Матрица Эйзенхауэра"],
        summary="Обновить настройки блока матрицы",
        description=(
            "Обновляет блок по `block`. "
            "`date_filters`: список any|overdue|today|tomorrow|later|no_deadline|with_deadline. "
            "`allowed_priorities`: список low|medium|high|critical."
        ),
    )
    def patch(self, request):
        ensure_default_matrix_settings(request.user)
        block = request.data.get("block")
        if not block:
            return Response({"block": ["Поле block обязательно."]}, status=400)
        item = get_object_or_404(MatrixBlockSetting, user=request.user, block=block)
        serializer = MatrixBlockSettingSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        changed = reassign_matrix_tasks(request.user)
        payload = dict(serializer.data)
        payload["reassigned_tasks"] = changed
        return Response(payload, status=200)


class RemindersDueAPIView(APIView):
    """Pending task reminders for client local notifications / polling."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Уведомления"],
        summary="Напоминания, которые пора показать",
        description=(
            "Задачи с `reminder_at <= now` (или `?until=`), ещё не ack. "
            "Клиент показывает notification, затем вызывает ack."
        ),
        parameters=[
            OpenApiParameter(
                name="until",
                type=str,
                required=False,
                description="ISO datetime. По умолчанию — сейчас.",
            ),
        ],
    )
    def get(self, request):
        activate_user_timezone(request.user)
        until = timezone.now()
        until_raw = request.query_params.get("until")
        if until_raw:
            try:
                until = datetime.fromisoformat(until_raw.replace("Z", "+00:00"))
                if timezone.is_naive(until):
                    until = timezone.make_aware(until)
            except ValueError:
                return Response({"until": ["Некорректный ISO datetime."]}, status=400)
        qs = pending_reminders_queryset(request.user, until=until).prefetch_related("attachments")
        return Response(
            {
                "until": until.isoformat(),
                "count": qs.count(),
                "tasks": TaskSerializer(
                    qs, many=True, context={"request": request, "now": timezone.localtime()}
                ).data,
            },
            status=200,
        )


class ReminderAckAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Уведомления"],
        summary="Подтвердить показ напоминания",
        description="Ставит `reminder_delivered_at`, чтобы reminder больше не приходил в due-список.",
    )
    def post(self, request, task_id: int):
        task = get_object_or_404(Task, id=task_id, user=request.user)
        task = ack_reminder(task)
        return Response(
            TaskSerializer(
                task, context={"request": request, "now": timezone.localtime()}
            ).data,
            status=200,
        )


class ReminderSnoozeAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Уведомления"],
        summary="Отложить напоминание",
        request=ReminderSnoozeSerializer,
    )
    def post(self, request, task_id: int):
        """Переносит reminder_at на указанное количество минут."""
        serializer = ReminderSnoozeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = get_object_or_404(Task, id=task_id, user=request.user)
        task = snooze_reminder(task, serializer.validated_data["minutes"])
        return Response(
            TaskSerializer(
                task,
                context={"request": request, "now": timezone.localtime()},
            ).data,
            status=200,
        )


class ReminderCompleteAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Уведомления"],
        summary="Завершить задачу из уведомления",
    )
    def post(self, request, task_id: int):
        """Завершает задачу и создаёт следующее повторение при необходимости."""
        task = get_object_or_404(Task, id=task_id, user=request.user)
        completed, next_task = complete_task_with_repeat(task)
        context = {"request": request, "now": timezone.localtime()}
        payload = TaskSerializer(completed, context=context).data
        payload["next_task"] = (
            TaskSerializer(next_task, context=context).data if next_task else None
        )
        return Response(payload, status=200)


class FCMDeviceListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Устройства / Push"],
        summary="Список устройств пользователя",
        responses={200: FCMDeviceSerializer(many=True)},
    )
    def get(self, request):
        """Возвращает устройства, зарегистрированные для FCM push."""
        devices = FCMDevice.objects.filter(user=request.user)
        return Response(FCMDeviceSerializer(devices, many=True).data, status=200)

    @extend_schema(
        tags=["Устройства / Push"],
        summary="Зарегистрировать или обновить FCM устройство",
        request=FCMDeviceSerializer,
        responses={200: FCMDeviceSerializer, 201: FCMDeviceSerializer},
    )
    def post(self, request):
        """Upsert устройства по user+device_id и обновление FCM token."""
        serializer = FCMDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        token = data["token"]
        device_id = data["device_id"]

        # One FCM token belongs to one current account/device record.
        FCMDevice.objects.filter(token=token).exclude(user=request.user).delete()
        device, created = FCMDevice.objects.update_or_create(
            user=request.user,
            device_id=device_id,
            defaults={
                "token": token,
                "name": data.get("name", ""),
                "platform": data["platform"],
                "app_version": data.get("app_version", ""),
                "is_active": True,
                "last_seen_at": timezone.now(),
            },
        )
        return Response(
            FCMDeviceSerializer(device).data,
            status=201 if created else 200,
        )


class FCMDeviceDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Устройства / Push"],
        summary="Отключить устройство",
    )
    def delete(self, request, device_id: int):
        """Удаляет FCM token устройства текущего пользователя."""
        device = get_object_or_404(FCMDevice, id=device_id, user=request.user)
        device.delete()
        return Response(status=204)


class NotificationPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100


class UserNotificationListAPIView(APIView):
    """In-app центр уведомлений: только уведомления текущего пользователя."""

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NotificationPagination

    @extend_schema(
        tags=["Уведомления"],
        summary="Список своих уведомлений",
        description=(
            "Возвращает только уведомления авторизованного пользователя. "
            "Фильтр: `?is_read=true|false`. Пагинация: `limit` / `offset`."
        ),
        parameters=[
            OpenApiParameter(
                name="is_read",
                type=str,
                required=False,
                description="true / false — фильтр по прочитанности",
            ),
            OpenApiParameter(name="limit", type=int, required=False),
            OpenApiParameter(name="offset", type=int, required=False),
        ],
        responses={200: UserNotificationSerializer(many=True)},
    )
    def get(self, request):
        qs = UserNotification.objects.filter(user=request.user)
        is_read = request.query_params.get("is_read")
        if is_read is not None:
            value = is_read.strip().lower()
            if value in {"1", "true", "yes"}:
                qs = qs.filter(is_read=True)
            elif value in {"0", "false", "no"}:
                qs = qs.filter(is_read=False)
            else:
                return Response(
                    {"is_read": ["Ожидается true или false."]},
                    status=400,
                )

        unread_count = UserNotification.objects.filter(
            user=request.user, is_read=False
        ).count()
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        data = UserNotificationSerializer(page, many=True).data
        response = paginator.get_paginated_response(data)
        response.data["unread_count"] = unread_count
        return response


class UserNotificationUnreadCountAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Уведомления"],
        summary="Количество непрочитанных уведомлений",
    )
    def get(self, request):
        count = UserNotification.objects.filter(
            user=request.user, is_read=False
        ).count()
        return Response({"unread_count": count}, status=200)


class UserNotificationReadAllAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Уведомления"],
        summary="Отметить все уведомления прочитанными",
    )
    def post(self, request):
        now = timezone.now()
        updated = UserNotification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True, read_at=now)
        return Response({"updated": updated, "unread_count": 0}, status=200)


class UserNotificationDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Уведомления"],
        summary="Получить одно уведомление",
        responses={200: UserNotificationSerializer},
    )
    def get(self, request, notification_id: int):
        item = get_object_or_404(
            UserNotification, id=notification_id, user=request.user
        )
        return Response(UserNotificationSerializer(item).data, status=200)

    @extend_schema(
        tags=["Уведомления"],
        summary="Удалить уведомление",
    )
    def delete(self, request, notification_id: int):
        item = get_object_or_404(
            UserNotification, id=notification_id, user=request.user
        )
        item.delete()
        return Response(status=204)


class UserNotificationReadAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Уведомления"],
        summary="Отметить уведомление прочитанным",
        responses={200: UserNotificationSerializer},
    )
    def post(self, request, notification_id: int):
        item = get_object_or_404(
            UserNotification, id=notification_id, user=request.user
        )
        if not item.is_read:
            item.is_read = True
            item.read_at = timezone.now()
            item.save(update_fields=["is_read", "read_at"])
        return Response(UserNotificationSerializer(item).data, status=200)


class AppSettingsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Настройки приложения"], summary="Получить настройки приложения")
    def get(self, request):
        settings_obj = get_or_create_user_settings(request.user)
        return Response(
            AppSettingsSerializer(settings_obj, context={"request": request}).data,
            status=200,
        )

    @extend_schema(
        tags=["Настройки приложения"],
        summary="Обновить настройки приложения",
        description="Язык, timezone (IANA), звуки, вибрация, видимость списков, вкладки.",
    )
    def patch(self, request):
        settings_obj = get_or_create_user_settings(request.user)
        serializer = AppSettingsSerializer(
            settings_obj, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        activate_user_timezone(request.user)
        return Response(serializer.data, status=200)


class SettingsStubActionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Настройки приложения"],
        summary="Заглушка для пунктов в разработке",
    )
    def post(self, request):
        return Response(
            {"detail": "Уже разрабатываем, скоро будет готово :)"},
            status=status.HTTP_202_ACCEPTED,
        )


class SoundCatalogAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Звуки"],
        summary="Каталог звуков",
        parameters=[
            OpenApiParameter(name="category", type=str, required=False),
        ],
    )
    def get(self, request):
        queryset = Sound.objects.filter(is_active=True).order_by("category", "sort_order", "key")
        category = request.query_params.get("category")
        if category:
            if category not in dict(Sound.Category.choices):
                return Response(
                    {
                        "category": [
                            f"Допустимые значения: {', '.join(dict(Sound.Category.choices))}."
                        ]
                    },
                    status=400,
                )
            queryset = queryset.filter(category=category)
        return Response(
            SoundSerializer(queryset, many=True, context={"request": request}).data,
            status=200,
        )


class PomodoroSettingsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Помодоро"], summary="Получить настройки помодоро")
    def get(self, request):
        settings_obj = get_or_create_pomodoro_settings(request.user)
        return Response(
            PomodoroSettingsSerializer(settings_obj, context={"request": request}).data,
            status=200,
        )

    @extend_schema(tags=["Помодоро"], summary="Обновить настройки помодоро")
    def patch(self, request):
        settings_obj = get_or_create_pomodoro_settings(request.user)
        serializer = PomodoroSettingsSerializer(
            settings_obj, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=200)


class PomodoroSessionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Помодоро"], summary="Список сессий помодоро")
    def get(self, request):
        sessions = PomodoroSession.objects.filter(user=request.user).select_related("task")
        return Response(PomodoroSessionSerializer(sessions, many=True).data, status=200)

    @extend_schema(tags=["Помодоро"], summary="Создать сессию помодоро")
    def post(self, request):
        serializer = PomodoroSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = serializer.save(user=request.user)
        return Response(PomodoroSessionSerializer(session).data, status=201)


class PomodoroSessionStateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Помодоро"], summary="Изменить состояние сессии")
    def post(self, request, session_id: int):
        session = get_object_or_404(PomodoroSession, id=session_id, user=request.user)
        serializer = PomodoroStateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_state = serializer.validated_data["state"]

        if new_state == PomodoroSession.State.RUNNING and not session.started_at:
            session.started_at = timezone.now()
        if new_state in {PomodoroSession.State.STOPPED, PomodoroSession.State.COMPLETED}:
            session.ended_at = timezone.now()
        session.state = new_state
        session.save(update_fields=["state", "started_at", "ended_at"])
        return Response(PomodoroSessionSerializer(session).data, status=200)


class HelpCenterAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    @extend_schema(
        tags=["Центр помощи"],
        summary="Получить FAQ с поиском",
        parameters=[
            OpenApiParameter(
                name="search",
                type=str,
                required=False,
                description="Поиск по вопросу и ответу.",
            )
        ],
        responses={200: FAQEntrySerializer(many=True)},
    )
    def get(self, request):
        """Возвращает активные FAQ и фильтрует их по search/q."""
        query = (request.query_params.get("search") or request.query_params.get("q") or "").strip()
        items = FAQEntry.objects.filter(is_active=True)
        if query:
            items = items.filter(
                Q(question__icontains=query) | Q(answer__icontains=query)
            )
        return Response(FAQEntrySerializer(items, many=True).data, status=200)

    @extend_schema(tags=["Центр помощи"], summary="Отправить сообщение в поддержку")
    def post(self, request):
        serializer = HelpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save(user=request.user)
        return Response(HelpRequestSerializer(ticket).data, status=201)


class LegalDocumentsAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=["Юридические документы"], summary="Список юридических документов")
    def get(self, request):
        docs = LegalDocument.objects.all()
        return Response(LegalDocumentSerializer(docs, many=True).data, status=200)
