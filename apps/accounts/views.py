import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import IntegrityError
from django.template.loader import render_to_string
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import PasswordResetRequest
from .serializers import (
    ChangePasswordSerializer,
    GoogleLoginSerializer,
    ForgotPasswordConfirmSerializer,
    ForgotPasswordRequestSerializer,
    ForgotPasswordVerifyCodeSerializer,
    ProfileSerializer,
    LoginSerializer,
    RegistrationSerializer,
)
from .utils import verify_firebase_id_token


User = get_user_model()


def _generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def _jwt_tokens_for_user(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


class TokenRefreshAPIView(TokenRefreshView):
    @extend_schema(
        tags=["Авторизация"],
        summary="Обновить access токен",
        description="Принимает refresh токен и возвращает новый access токен (и refresh, если включена ротация).",
        responses={200: OpenApiResponse(description="Access токен обновлён")},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class РегистрацияAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser]

    @extend_schema(
        tags=["Авторизация"],
        summary="Регистрация пользователя",
        description="Создаёт нового пользователя по email и паролю.",
        request=RegistrationSerializer,
        responses={201: OpenApiResponse(description="Пользователь создан")},
    )
    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except IntegrityError:
            return Response(
                {"email": ["Пользователь с таким email уже существует"]},
                status=400,
            )
        tokens = _jwt_tokens_for_user(user)
        return Response({"user": ProfileSerializer(user).data, "tokens": tokens}, status=201)


class ВходAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser]

    @extend_schema(
        tags=["Авторизация"],
        summary="Вход по email и паролю",
        description="Возвращает JWT access/refresh токены.",
        request=LoginSerializer,
        responses={200: OpenApiResponse(description="Токены выданы")},
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        tokens = _jwt_tokens_for_user(user)
        return Response({"tokens": tokens}, status=200)


class GoogleLoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser]

    @extend_schema(
        tags=["Авторизация"],
        summary="Вход через Google (Firebase ID Token)",
        description="Принимает Firebase ID Token, проверяет его через Firebase Admin SDK, создаёт/находит пользователя и возвращает JWT токены.",
        request=GoogleLoginSerializer,
        responses={200: OpenApiResponse(description="Токены выданы")},
    )
    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        id_token = serializer.validated_data["firebase_token"]

        decoded = verify_firebase_id_token(id_token)
        email = decoded.get("email")
        if not email:
            return Response({"detail": "В токене отсутствует email"}, status=400)

        user, created = User.objects.get_or_create(email=email, defaults={"username": email})
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])

        tokens = _jwt_tokens_for_user(user)
        return Response({"tokens": tokens, "user": ProfileSerializer(user).data}, status=200)


class ПрофильAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    @extend_schema(
        tags=["Профиль"],
        summary="Получить профиль",
        description="Возвращает данные текущего пользователя.",
        responses={200: ProfileSerializer},
    )
    def get(self, request):
        return Response(ProfileSerializer(request.user, context={"request": request}).data, status=200)

    @extend_schema(
        tags=["Профиль"],
        summary="Обновить профиль (multipart/form-data)",
        description="Обновляет имя/фамилию/аватар. Для аватара используйте multipart/form-data.",
        request=ProfileSerializer,
        responses={200: ProfileSerializer},
    )
    def put(self, request):
        serializer = ProfileSerializer(instance=request.user, data=request.data, partial=False, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=200)

    @extend_schema(
        tags=["Профиль"],
        summary="Частично обновить профиль (multipart/form-data)",
        description="Частичное обновление профиля. Для аватара используйте multipart/form-data.",
        request=ProfileSerializer,
        responses={200: ProfileSerializer},
    )
    def patch(self, request):
        serializer = ProfileSerializer(
            instance=request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=200)


class ChangePasswordAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]

    @extend_schema(
        tags=["Авторизация"],
        summary="Сменить пароль (только new_password)",
        description=(
            "Требуется Bearer access. Принимает только `new_password` и устанавливает его "
            "текущему пользователю без проверки старого пароля."
        ),
        request=ChangePasswordSerializer,
        responses={200: OpenApiResponse(description="Пароль обновлён")},
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"user": request.user},
        )
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response({"detail": "Пароль обновлён"}, status=200)


class ЗабылиПарольЗапросAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser]

    @extend_schema(
        tags=["Восстановление пароля"],
        summary="Запросить код для сброса пароля",
        description="Отправляет 6-значный код на email. Если пользователь не найден — ответ всё равно 200 (без раскрытия).",
        request=ForgotPasswordRequestSerializer,
        responses={200: OpenApiResponse(description="Код отправлен")},
    )
    def post(self, request):
        serializer = ForgotPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        def _create_request_and_send(user):
            code = _generate_code()
            ttl = getattr(settings, "PASSWORD_RESET_CODE_TTL_SECONDS", 600)
            pr = PasswordResetRequest.objects.create(
                user=user,
                email=email,
                code=code,
                expires_at=timezone.now() + timedelta(seconds=ttl),
            )

            html = render_to_string("emails/password_reset.html", {"code": code, "email": email})
            send_mail(
                subject="Код для сброса пароля",
                message=f"Ваш код: {code}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html,
                fail_silently=not getattr(settings, "DEBUG", False),
            )
            return pr

        try:
            user = User.objects.get(email=email)
            _create_request_and_send(user)
        except User.DoesNotExist:
            pass

        return Response({"detail": "Если email существует, код отправлен"}, status=200)


class ЗабылиПарольПроверкаКодаAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser]

    @extend_schema(
        tags=["Восстановление пароля"],
        summary="Проверить код и получить токен сброса",
        description="Проверяет код. В ответ отдаёт `reset_token`, который нужно использовать для установки нового пароля.",
        request=ForgotPasswordVerifyCodeSerializer,
        responses={
            200: OpenApiResponse(description="Токен сброса выдан"),
            400: OpenApiResponse(description="Неверный код или истёк срок"),
        },
    )
    def post(self, request):
        serializer = ForgotPasswordVerifyCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        code = serializer.validated_data["code"]

        def _find():
            return (
                PasswordResetRequest.objects.filter(email=email, code=code, used_at__isnull=True)
                .order_by("-created_at")
                .first()
            )

        pr = _find()
        if not pr or pr.is_expired:
            return Response({"detail": "Неверный код или срок истёк"}, status=400)

        return Response({"reset_token": str(pr.reset_token)}, status=200)


class ЗабылиПарольНовыйПарольAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser]

    @extend_schema(
        tags=["Восстановление пароля"],
        summary="Установить новый пароль по токену",
        description="Устанавливает новый пароль по `reset_token`.",
        request=ForgotPasswordConfirmSerializer,
        responses={200: OpenApiResponse(description="Пароль обновлён")},
    )
    def post(self, request):
        serializer = ForgotPasswordConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reset_token = serializer.validated_data["reset_token"]
        new_password = serializer.validated_data["new_password"]

        def _use_token():
            pr = PasswordResetRequest.objects.filter(reset_token=reset_token, used_at__isnull=True).first()
            if not pr or pr.is_expired:
                return None
            user = pr.user
            user.set_password(new_password)
            user.save(update_fields=["password"])
            pr.used_at = timezone.now()
            pr.save(update_fields=["used_at"])
            return user

        user = _use_token()
        if not user:
            return Response({"detail": "Токен недействителен или истёк"}, status=400)

        return Response({"detail": "Пароль обновлён"}, status=200)

