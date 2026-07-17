from django.conf import settings
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.planner.models import PremiumFeatureFlag
from apps.planner.serializers import AppSettingsSerializer, PremiumFeatureFlagSerializer
from apps.planner.views import get_or_create_user_settings

from . import robokassa
from .models import Payment, Tariff
from .serializers import (
    PaymentSerializer,
    PremiumCheckoutSerializer,
    PremiumTrialSerializer,
    SubscriptionSerializer,
    TariffSerializer,
)
from .services import (
    apply_successful_payment,
    cancel_subscription,
    create_checkout_payment,
    get_or_create_subscription,
    record_consent,
    start_promo,
)


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class TariffListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Премиум"], summary="Список тарифов", responses={200: TariffSerializer(many=True)})
    def get(self, request):
        tariffs = Tariff.objects.filter(is_active=True)
        return Response(TariffSerializer(tariffs, many=True).data, status=200)


class SubscriptionStatusAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Премиум"], summary="Статус подписки")
    def get(self, request):
        sub = get_or_create_subscription(request.user)
        return Response(SubscriptionSerializer(sub).data, status=200)


class PremiumCheckoutAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Премиум"],
        summary="Создать ссылку на оплату (Robokassa)",
        description=(
            "Создаёт материнский платёж. Для рекуррентных тарифов обязателен "
            "`recurring_consent=true` (чекбокс, по умолчанию OFF на клиенте)."
        ),
        request=PremiumCheckoutSerializer,
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
            payment = create_checkout_payment(
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
                "checkout_url": payment.checkout_url,
                "provider": "robokassa",
                "payment": PaymentSerializer(payment).data,
            },
            status=200,
        )


class PremiumTrialAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Премиум"],
        summary="Запустить промо-период",
        description=(
            "Вариант 2: промо считается на нашем бэкенде. "
            "Robokassa промо в кабинете не поддерживает."
        ),
        request=PremiumTrialSerializer,
    )
    def post(self, request):
        serializer = PremiumTrialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tariff = Tariff.objects.filter(code=serializer.validated_data["tariff"], is_active=True).first()
        if not tariff:
            return Response({"detail": "Тариф не найден."}, status=400)
        consent = None
        # Consent обязателен только когда Robokassa recurring реально включён.
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
        except ValueError as exp:
            return Response({"detail": str(exp)}, status=400)
        return Response(SubscriptionSerializer(sub).data, status=200)


class PremiumCancelAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Премиум"], summary="Отменить автопродление")
    def post(self, request):
        sub = cancel_subscription(request.user)
        return Response(SubscriptionSerializer(sub).data, status=200)


@method_decorator(csrf_exempt, name="dispatch")
class RobokassaResultAPIView(APIView):
    """ResultURL — сервер Robokassa. Auth не нужен, проверка по SignatureValue."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    parser_classes = [FormParser, MultiPartParser, JSONParser]

    @extend_schema(
        tags=["Премиум"],
        summary="Robokassa ResultURL callback",
        description="Вызывается Robokassa после оплаты. Ответ должен быть OK{InvId}.",
    )
    def post(self, request):
        return self._handle_result(request)

    def get(self, request):
        # Кабинет часто шлёт Result URL методом GET (query string).
        return self._handle_result(request)

    def _handle_result(self, request):
        # POST → request.data; GET → query_params. Объединяем оба.
        data = {}
        if hasattr(request, "query_params"):
            data.update({k: v for k, v in request.query_params.items()})
        if getattr(request, "data", None):
            try:
                data.update({k: v for k, v in request.data.items()})
            except Exception:
                pass
        # Fallback для сырого QueryDict
        if hasattr(request, "GET") and request.GET:
            data.update({k: v for k, v in request.GET.items()})
        if hasattr(request, "POST") and request.POST:
            data.update({k: v for k, v in request.POST.items()})

        out_sum = str(data.get("OutSum") or data.get("out_sum") or "")
        inv_id = data.get("InvId") or data.get("InvoiceID") or data.get("inv_id")
        signature = str(
            data.get("SignatureValue")
            or data.get("signaturevalue")
            or data.get("Signature")
            or ""
        )

        logger = __import__("logging").getLogger(__name__)
        logger.info(
            "Robokassa ResultURL method=%s InvId=%s OutSum=%s keys=%s",
            request.method,
            inv_id,
            out_sum,
            sorted(data.keys()),
        )

        if not out_sum or not inv_id or not signature:
            logger.warning("Robokassa ResultURL bad request: missing fields data=%s", data)
            return HttpResponse("bad request", status=400)

        try:
            invoice_id = int(inv_id)
        except (TypeError, ValueError):
            return HttpResponse("bad inv", status=400)

        shp = robokassa.extract_shp(data)
        if not robokassa.verify_result_signature(out_sum, invoice_id, signature, shp=shp):
            logger.warning(
                "Robokassa ResultURL bad sign InvId=%s OutSum=%s shp=%s",
                invoice_id,
                out_sum,
                shp,
            )
            return HttpResponse("bad sign", status=400)

        payment = Payment.objects.filter(invoice_id=invoice_id).select_related("tariff", "user").first()
        if not payment:
            logger.warning("Robokassa ResultURL payment not found InvId=%s", invoice_id)
            return HttpResponse("not found", status=404)

        apply_successful_payment(payment, raw=dict(data))
        logger.info(
            "Robokassa ResultURL OK InvId=%s user=%s",
            invoice_id,
            payment.user_id,
        )
        return HttpResponse(f"OK{invoice_id}", content_type="text/plain")


class PremiumActivateAPIView(APIView):
    """Только для DEBUG / ручного теста. В production оплату подтверждает ResultURL."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Премиум"], summary="DEV: активировать премиум без оплаты")
    def post(self, request):
        if not getattr(settings, "DEBUG", False):
            return Response(
                {"detail": "В production премиум активируется только через Robokassa ResultURL."},
                status=403,
            )
        settings_obj = get_or_create_user_settings(request.user)
        from django.utils import timezone

        settings_obj.is_premium = True
        settings_obj.premium_activated_at = timezone.now()
        settings_obj.save(update_fields=["is_premium", "premium_activated_at"])
        sub = get_or_create_subscription(request.user)
        sub.status = sub.Status.ACTIVE
        sub.save(update_fields=["status", "updated_at"])
        return Response(AppSettingsSerializer(settings_obj, context={"request": request}).data, status=200)


class PremiumFeaturesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Премиум"], summary="Feature flags премиума")
    def get(self, request):
        flags = PremiumFeatureFlag.objects.filter(is_enabled=True).order_by("key")
        return Response(PremiumFeatureFlagSerializer(flags, many=True).data, status=200)
