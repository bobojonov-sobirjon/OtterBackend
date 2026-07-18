"""Mobile app premium APIs (Robokassa SDK). Web/desktop use apps.billing.views."""

from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.planner.models import PremiumFeatureFlag
from apps.planner.serializers import PremiumFeatureFlagSerializer

from . import robokassa
from .models import Payment, Tariff
from .serializers import (
    MobileCheckoutResponseSerializer,
    PaymentSerializer,
    PremiumCheckoutSerializer,
    PremiumTrialSerializer,
    SubscriptionSerializer,
    TariffSerializer,
)
from .services import (
    cancel_subscription,
    create_mobile_sdk_payment,
    get_or_create_subscription,
    record_consent,
    start_promo,
)
from .views import _client_ip


class MobileTariffListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Mobile / Премиум"], summary="Список тарифов (app)")
    def get(self, request):
        tariffs = Tariff.objects.filter(is_active=True)
        return Response(TariffSerializer(tariffs, many=True).data, status=200)


class MobileSubscriptionStatusAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Mobile / Премиум"], summary="Статус подписки (app)")
    def get(self, request):
        sub = get_or_create_subscription(request.user)
        return Response(SubscriptionSerializer(sub).data, status=200)


class MobilePremiumCheckoutAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Mobile / Премиум"],
        summary="Создать платёж для Robokassa SDK",
        description=(
            "Возвращает параметры и SignatureValue для официального Robokassa SDK "
            "(Android/iOS). Пароли Robokassa клиенту не передаются."
        ),
        request=PremiumCheckoutSerializer,
        responses={200: MobileCheckoutResponseSerializer},
    )
    def post(self, request):
        serializer = PremiumCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["tariff"]
        tariff = Tariff.objects.filter(code=code, is_active=True).first()
        if not tariff:
            return Response({"detail": "Тариф не найден."}, status=400)
        if not robokassa.is_configured():
            return Response(
                {"detail": "Robokassa ещё не настроена на сервере (проверьте .env)."},
                status=503,
            )
        try:
            payment, sdk_params = create_mobile_sdk_payment(
                user=request.user,
                tariff=tariff,
                recurring_consent=serializer.validated_data.get("recurring_consent", False),
                offer_version=serializer.validated_data.get("offer_version", ""),
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        except robokassa.RobokassaError as exc:
            return Response({"detail": str(exc)}, status=503)

        return Response(
            {
                "provider": "robokassa",
                "payment": PaymentSerializer(payment).data,
                "sdk": sdk_params,
            },
            status=200,
        )


class MobilePremiumTrialAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Mobile / Премиум"],
        summary="Запустить промо-период (app)",
        request=PremiumTrialSerializer,
    )
    def post(self, request):
        serializer = PremiumTrialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tariff = Tariff.objects.filter(code=serializer.validated_data["tariff"], is_active=True).first()
        if not tariff:
            return Response({"detail": "Тариф не найден."}, status=400)
        consent = None
        if tariff.is_recurring and robokassa.recurring_enabled():
            if not serializer.validated_data.get("recurring_consent"):
                return Response(
                    {"detail": "Нужно согласие на автоматические списания (чекбокс)."},
                    status=400,
                )
            consent = record_consent(
                user=request.user,
                tariff=tariff,
                offer_version=serializer.validated_data.get("offer_version", ""),
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        elif tariff.is_recurring and serializer.validated_data.get("recurring_consent"):
            consent = record_consent(
                user=request.user,
                tariff=tariff,
                offer_version=serializer.validated_data.get("offer_version", ""),
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        try:
            sub = start_promo(user=request.user, tariff=tariff, consent=consent)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(SubscriptionSerializer(sub).data, status=200)


class MobilePremiumCancelAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Mobile / Премиум"], summary="Отменить автопродление (app)")
    def post(self, request):
        sub = cancel_subscription(request.user)
        return Response(SubscriptionSerializer(sub).data, status=200)


class MobilePaymentStatusAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Mobile / Премиум"],
        summary="Статус платежа по InvId (app)",
        description=(
            "После закрытия Robokassa SDK опрашивайте этот endpoint, "
            "пока status не станет paid (или истечёт таймаут)."
        ),
        responses={200: PaymentSerializer},
    )
    def get(self, request, invoice_id: int):
        payment = Payment.objects.filter(
            user=request.user,
            invoice_id=invoice_id,
            channel=Payment.Channel.MOBILE_SDK,
        ).first()
        if not payment:
            return Response({"detail": "Платёж не найден."}, status=404)
        return Response(PaymentSerializer(payment).data, status=200)


class MobileLatestPendingPaymentAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Mobile / Премиум"],
        summary="Последний ожидающий платёж (app)",
        responses={200: PaymentSerializer},
    )
    def get(self, request):
        payment = (
            Payment.objects.filter(
                user=request.user,
                channel=Payment.Channel.MOBILE_SDK,
                status=Payment.Status.PENDING,
            )
            .order_by("-created_at")
            .first()
        )
        if not payment:
            return Response({"detail": "Нет ожидающих платежей."}, status=404)
        return Response(PaymentSerializer(payment).data, status=200)


class MobilePremiumFeaturesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Mobile / Премиум"], summary="Feature flags премиума (app)")
    def get(self, request):
        flags = PremiumFeatureFlag.objects.filter(is_enabled=True).order_by("key")
        return Response(PremiumFeatureFlagSerializer(flags, many=True).data, status=200)
