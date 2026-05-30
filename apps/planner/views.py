from datetime import datetime

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AppSettings,
    LegalDocument,
    MatrixBlockSetting,
    PomodoroSession,
    PomodoroSettings,
    PremiumFeatureFlag,
    Task,
)
from .serializers import (
    AppSettingsSerializer,
    HelpRequestSerializer,
    LegalDocumentSerializer,
    MatrixBlockSettingSerializer,
    PomodoroSessionSerializer,
    PomodoroSettingsSerializer,
    PomodoroStateUpdateSerializer,
    PremiumCheckoutSerializer,
    PremiumFeatureFlagSerializer,
    TaskSerializer,
    date_range_for_view,
    split_tasks_by_default_groups,
)


def get_or_create_user_settings(user):
    """Создает дефолтные настройки приложения, если их еще нет у пользователя."""
    return AppSettings.objects.get_or_create(
        user=user,
        defaults={
            "bottom_tabs": ["tasks", "calendar", "matrix", "pomodoro", "settings"],
        },
    )[0]


def get_or_create_pomodoro_settings(user):
    """Создает дефолтные настройки помодоро, если пользователь их еще не настраивал."""
    return PomodoroSettings.objects.get_or_create(user=user)[0]


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
            defaults={"title": title, "allowed_priorities": [], "date_filter": ""},
        )


@extend_schema_view(
    list=extend_schema(
        tags=["Задачи"],
        summary="Список задач",
        description=(
            "Возвращает список задач текущего пользователя. "
            "Поддерживаются фильтры `search`, `is_completed`, `matrix_block`."
        ),
    ),
    retrieve=extend_schema(
        tags=["Задачи"],
        summary="Детальная информация по задаче",
        description="Возвращает полную информацию по одной задаче пользователя.",
    ),
    create=extend_schema(
        tags=["Задачи"],
        summary="Создание задачи",
        description=(
            "Создаёт новую задачу. Если не передан `due_at`, задача попадёт в группу "
            "`Без срока`. Поддерживается загрузка изображения задачи."
        ),
    ),
    update=extend_schema(
        tags=["Задачи"],
        summary="Полное обновление задачи",
        description="Полностью заменяет данные существующей задачи.",
    ),
    partial_update=extend_schema(
        tags=["Задачи"],
        summary="Частичное обновление задачи",
        description="Обновляет только переданные поля задачи.",
    ),
    destroy=extend_schema(
        tags=["Задачи"],
        summary="Удаление задачи",
        description="Удаляет задачу пользователя (аналог свайпа влево в мобильном приложении).",
    ),
)
class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        """Возвращает задачи текущего пользователя с фильтрами поиска и статуса."""
        queryset = Task.objects.filter(user=self.request.user).order_by("is_completed", "due_at", "-created_at")
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search))
        is_completed = self.request.query_params.get("is_completed")
        if is_completed in {"true", "false"}:
            queryset = queryset.filter(is_completed=(is_completed == "true"))
        matrix_block = self.request.query_params.get("matrix_block")
        if matrix_block:
            queryset = queryset.filter(matrix_block=matrix_block)
        return queryset

    def perform_create(self, serializer):
        """Привязывает создаваемую задачу к текущему пользователю."""
        serializer.save(user=self.request.user)

    @extend_schema(
        tags=["Задачи"],
        summary="Группировка задач по системным спискам",
        description=(
            "Возвращает задачи в группах `Просрочено`, `Сегодня`, `Завтра`, `Позже`, "
            "`Без срока`, `Выполнено` с количеством задач в каждой группе."
        ),
        responses={200: OpenApiResponse(description="Группы задач успешно сформированы.")},
    )
    @action(detail=False, methods=["get"], url_path="grouped")
    def grouped(self, request):
        """Возвращает задачи в формате групп по умолчанию из ТЗ."""
        tasks = list(Task.objects.filter(user=request.user))
        grouped = split_tasks_by_default_groups(tasks)
        titles = {
            "overdue": "Просрочено",
            "today": "Сегодня",
            "tomorrow": "Завтра",
            "later": "Позже",
            "no_deadline": "Без срока",
            "completed": "Выполнено",
        }
        data = [
            {
                "key": key,
                "title": titles[key],
                "count": len(items),
                "tasks": TaskSerializer(items, many=True, context={"request": request}).data,
            }
            for key, items in grouped.items()
        ]
        return Response(data, status=200)

    @extend_schema(
        tags=["Задачи"],
        summary="Отметить задачу выполненной",
        description="Устанавливает статус выполнения задачи (аналог свайпа вправо).",
    )
    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        """Ставит задаче отметку выполнения как при свайпе вправо в мобильном приложении."""
        task = self.get_object()
        task.mark_completed(True)
        task.save(update_fields=["is_completed", "completed_at", "updated_at"])
        return Response(TaskSerializer(task, context={"request": request}).data, status=200)

    @extend_schema(
        tags=["Задачи"],
        summary="Снять отметку выполнения",
        description="Переводит задачу обратно в активное состояние.",
    )
    @action(detail=True, methods=["post"], url_path="uncomplete")
    def uncomplete(self, request, pk=None):
        """Снимает отметку выполнения, чтобы вернуть задачу в активные списки."""
        task = self.get_object()
        task.mark_completed(False)
        task.save(update_fields=["is_completed", "completed_at", "updated_at"])
        return Response(TaskSerializer(task, context={"request": request}).data, status=200)


class CalendarAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Календарь"],
        summary="Задачи для календарного представления",
        description=(
            "Возвращает задачи в диапазоне выбранного вида календаря: "
            "`day`, `week`, `month`, `year`."
        ),
        parameters=[
            OpenApiParameter(
                name="view",
                type=str,
                required=True,
                description="Режим календаря: day | week | month | year.",
            ),
            OpenApiParameter(
                name="date",
                type=str,
                required=True,
                description="Опорная дата в формате YYYY-MM-DD.",
            ),
        ],
        responses={
            200: OpenApiResponse(description="Диапазон и задачи для календаря успешно получены."),
            400: OpenApiResponse(description="Некорректные параметры `view` или `date`."),
        },
    )
    def get(self, request):
        """Отдает задачи в выбранном диапазоне календаря для отображения в UI."""
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

        tasks = Task.objects.filter(
            user=request.user,
        ).filter(
            Q(start_at__gte=start_dt, start_at__lt=end_dt)
            | Q(due_at__gte=start_dt, due_at__lt=end_dt)
            | Q(start_at__isnull=True, due_at__isnull=True)
        )
        return Response(
            {
                "view": view_mode,
                "date": date_str,
                "range_start": start.isoformat(),
                "range_end": end.isoformat(),
                "tasks": TaskSerializer(tasks, many=True, context={"request": request}).data,
            },
            status=200,
        )


class MatrixAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Матрица Эйзенхауэра"],
        summary="Получить блоки матрицы с задачами",
        description=(
            "Возвращает 4 блока матрицы Эйзенхауэра и задачи, "
            "распределённые по этим блокам."
        ),
    )
    def get(self, request):
        """Возвращает 4 блока матрицы и задачи в каждом блоке."""
        ensure_default_matrix_settings(request.user)
        settings_qs = MatrixBlockSetting.objects.filter(user=request.user).order_by("id")
        tasks = Task.objects.filter(user=request.user, is_completed=False)

        payload = []
        for block_setting in settings_qs:
            block_tasks = tasks.filter(matrix_block=block_setting.block)
            payload.append(
                {
                    "block": block_setting.block,
                    "title": block_setting.title,
                    "allowed_priorities": block_setting.allowed_priorities,
                    "date_filter": block_setting.date_filter,
                    "count": block_tasks.count(),
                    "tasks": TaskSerializer(block_tasks, many=True, context={"request": request}).data,
                }
            )
        return Response(payload, status=200)


class MatrixBlockSettingsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Матрица Эйзенхауэра"],
        summary="Получить настройки блоков матрицы",
        description="Возвращает пользовательские настройки всех четырёх блоков матрицы.",
    )
    def get(self, request):
        """Возвращает пользовательские настройки всех блоков матрицы."""
        ensure_default_matrix_settings(request.user)
        items = MatrixBlockSetting.objects.filter(user=request.user).order_by("id")
        return Response(MatrixBlockSettingSerializer(items, many=True).data, status=200)

    @extend_schema(
        tags=["Матрица Эйзенхауэра"],
        summary="Обновить настройки блока матрицы",
        description=(
            "Обновляет один блок матрицы по полю `block`. "
            "Можно изменить название, приоритеты и фильтр по дате."
        ),
    )
    def patch(self, request):
        """Обновляет один блок матрицы по его коду block."""
        ensure_default_matrix_settings(request.user)
        block = request.data.get("block")
        if not block:
            return Response({"block": ["Поле block обязательно."]}, status=400)
        item = get_object_or_404(MatrixBlockSetting, user=request.user, block=block)
        serializer = MatrixBlockSettingSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=200)


class AppSettingsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Настройки приложения"],
        summary="Получить настройки приложения",
        description="Возвращает текущие пользовательские настройки интерфейса и уведомлений.",
    )
    def get(self, request):
        """Отдает пользовательские настройки, которые управляют вкладками и системными параметрами."""
        settings_obj = get_or_create_user_settings(request.user)
        return Response(AppSettingsSerializer(settings_obj).data, status=200)

    @extend_schema(
        tags=["Настройки приложения"],
        summary="Обновить настройки приложения",
        description="Частично обновляет настройки пользователя (звук, вкладки, язык и т.д.).",
    )
    def patch(self, request):
        """Обновляет только переданные поля настроек приложения."""
        settings_obj = get_or_create_user_settings(request.user)
        serializer = AppSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=200)


class SettingsStubActionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Настройки приложения"],
        summary="Заглушка для пунктов в разработке",
        description="Единый эндпоинт для пунктов меню, которые ещё находятся в разработке.",
    )
    def post(self, request):
        """Возвращает единый ответ для пунктов настроек, которые пока в разработке."""
        return Response({"detail": "Уже разрабатываем, скоро будет готово :)"},
                        status=status.HTTP_202_ACCEPTED)


class PomodoroSettingsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Помодоро"],
        summary="Получить настройки помодоро",
        description="Возвращает параметры таймера: длительность, звук и режим экрана блокировки.",
    )
    def get(self, request):
        """Возвращает параметры таймера помодоро текущего пользователя."""
        settings_obj = get_or_create_pomodoro_settings(request.user)
        return Response(PomodoroSettingsSerializer(settings_obj).data, status=200)

    @extend_schema(
        tags=["Помодоро"],
        summary="Обновить настройки помодоро",
        description="Обновляет пользовательские параметры таймера помодоро.",
    )
    def patch(self, request):
        """Обновляет длительность, звук и параметры отображения таймера."""
        settings_obj = get_or_create_pomodoro_settings(request.user)
        serializer = PomodoroSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=200)


class PomodoroSessionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Помодоро"],
        summary="Список сессий помодоро",
        description="Возвращает историю созданных сессий помодоро для текущего пользователя.",
    )
    def get(self, request):
        """Возвращает историю сессий помодоро пользователя."""
        sessions = PomodoroSession.objects.filter(user=request.user).select_related("task")
        return Response(PomodoroSessionSerializer(sessions, many=True).data, status=200)

    @extend_schema(
        tags=["Помодоро"],
        summary="Создать сессию помодоро",
        description="Создаёт новую сессию помодоро с выбранной задачей и длительностью.",
    )
    def post(self, request):
        """Создает новую сессию помодоро с выбранной задачей и длительностью."""
        serializer = PomodoroSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = serializer.save(user=request.user)
        return Response(PomodoroSessionSerializer(session).data, status=201)


class PomodoroSessionStateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Помодоро"],
        summary="Изменить состояние сессии",
        description=(
            "Переводит сессию в одно из состояний: `running`, `paused`, "
            "`stopped`, `completed`."
        ),
    )
    def post(self, request, session_id: int):
        """Переключает состояние сессии для кнопок старт, пауза, стоп и завершение."""
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
        summary="Получить FAQ",
        description="Возвращает базовый список часто задаваемых вопросов и ответов.",
    )
    def get(self, request):
        """Отдает минимальный FAQ, чтобы мобильное приложение могло построить раздел помощи."""
        data = [
            {"question": "Как создать задачу?", "answer": "Нажмите кнопку + на главной странице."},
            {"question": "Как работает помодоро?", "answer": "Выберите задачу, нажмите старт и работайте до сигнала."},
        ]
        return Response(data, status=200)

    @extend_schema(
        tags=["Центр помощи"],
        summary="Отправить сообщение в поддержку",
        description="Создаёт обращение в поддержку с текстом и опциональным скриншотом.",
    )
    def post(self, request):
        """Принимает сообщение пользователя и скриншот для передачи в поддержку."""
        serializer = HelpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save(user=request.user)
        return Response(HelpRequestSerializer(ticket).data, status=201)


class PremiumCheckoutAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Премиум"],
        summary="Создать ссылку на оплату премиум",
        description="Формирует URL для перехода в платёжный шлюз Robokassa.",
    )
    def post(self, request):
        """Формирует заглушку ссылки на оплату через Robokassa для мобильного клиента."""
        serializer = PremiumCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tariff = serializer.validated_data["tariff"]
        fake_url = f"https://auth.robokassa.ru/Merchant/Index.aspx?tariff={tariff}&user={request.user.id}"
        return Response({"checkout_url": fake_url, "provider": "robokassa"}, status=200)


class PremiumActivateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Премиум"],
        summary="Активировать премиум",
        description="Активирует премиум-статус пользователя после успешного подтверждения оплаты.",
    )
    def post(self, request):
        """Активирует премиум пользователю после подтверждения оплаты от платежного сервиса."""
        settings_obj = get_or_create_user_settings(request.user)
        settings_obj.is_premium = True
        settings_obj.premium_activated_at = timezone.now()
        settings_obj.save(update_fields=["is_premium", "premium_activated_at"])
        return Response(AppSettingsSerializer(settings_obj).data, status=200)


class PremiumFeaturesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Премиум"],
        summary="Список флагов премиум-функций",
        description="Возвращает включенные feature-flag'и для гибкого управления платным функционалом.",
    )
    def get(self, request):
        """Возвращает список фич, которые можно гибко включать в премиум на бэкенде."""
        flags = PremiumFeatureFlag.objects.filter(is_enabled=True).order_by("key")
        return Response(PremiumFeatureFlagSerializer(flags, many=True).data, status=200)


class LegalDocumentsAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Юридические документы"],
        summary="Список юридических документов",
        description=(
            "Возвращает тексты документов: оферта, политика конфиденциальности, "
            "политика возвратов и согласие на обработку персональных данных."
        ),
    )
    def get(self, request):
        """Отдает текст оферты, политики конфиденциальности и других обязательных документов."""
        docs = LegalDocument.objects.all()
        return Response(LegalDocumentSerializer(docs, many=True).data, status=200)

