"""Subscription / premium business logic (promo on our side)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import robokassa
from .models import Payment, RecurringConsent, Subscription, Tariff


def get_or_create_subscription(user) -> Subscription:
    sub, _ = Subscription.objects.get_or_create(user=user)
    return sub


def sync_app_settings_premium(user, *, is_premium: bool, premium_until=None, activated_at=None):
    from apps.planner.views import get_or_create_user_settings

    settings_obj = get_or_create_user_settings(user)
    settings_obj.is_premium = is_premium
    update_fields = ["is_premium"]
    if activated_at is not None:
        settings_obj.premium_activated_at = activated_at
        update_fields.append("premium_activated_at")
    if hasattr(settings_obj, "premium_until"):
        settings_obj.premium_until = premium_until
        update_fields.append("premium_until")
    settings_obj.save(update_fields=update_fields)
    return settings_obj


def _next_invoice_id() -> int:
    last = Payment.objects.order_by("-invoice_id").values_list("invoice_id", flat=True).first()
    return int(last or 100000) + 1


def record_consent(
    *,
    user,
    tariff: Tariff,
    offer_version: str = "",
    ip_address: str | None = None,
    user_agent: str = "",
) -> RecurringConsent:
    RecurringConsent.objects.filter(user=user, is_active=True).update(
        is_active=False,
        revoked_at=timezone.now(),
    )
    return RecurringConsent.objects.create(
        user=user,
        tariff=tariff,
        offer_version=offer_version or "",
        agreed=True,
        ip_address=ip_address,
        user_agent=user_agent or "",
        is_active=True,
    )


def start_promo(*, user, tariff: Tariff, consent: RecurringConsent | None = None) -> Subscription:
    """Вариант 2: промо-период на нашей стороне, без списания."""
    if tariff.promo_days <= 0:
        raise ValueError("У тарифа нет промо-периода.")

    now = timezone.now()
    sub = get_or_create_subscription(user)
    if sub.status in {Subscription.Status.TRIAL, Subscription.Status.ACTIVE} and sub.is_premium_now:
        raise ValueError("Подписка уже активна.")

    sub.tariff = tariff
    sub.status = Subscription.Status.TRIAL
    sub.promo_until = now + timedelta(days=tariff.promo_days)
    sub.premium_until = sub.promo_until
    sub.recurring_enabled = bool(tariff.is_recurring and consent is not None)
    sub.cancelled_at = None
    sub.save()

    sync_app_settings_premium(
        user,
        is_premium=True,
        premium_until=sub.premium_until,
        activated_at=now,
    )
    return sub


@transaction.atomic
def _prepare_checkout_payment(
    *,
    user,
    tariff: Tariff,
    recurring_consent: bool = False,
    offer_version: str = "",
    ip_address: str | None = None,
    user_agent: str = "",
    channel: str = Payment.Channel.WEB,
) -> tuple[Payment, bool]:
    """Создаёт pending-платёж. Возвращает (payment, use_robokassa_recurring)."""
    use_robokassa_recurring = bool(tariff.is_recurring and robokassa.recurring_enabled())

    if use_robokassa_recurring:
        if not recurring_consent:
            raise ValueError("Нужно согласие на автоматические списания (чекбокс).")
        record_consent(
            user=user,
            tariff=tariff,
            offer_version=offer_version,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    elif tariff.is_recurring and recurring_consent:
        record_consent(
            user=user,
            tariff=tariff,
            offer_version=offer_version,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    invoice_id = _next_invoice_id()
    kind = Payment.Kind.INITIAL if use_robokassa_recurring else Payment.Kind.ONE_TIME
    description = f"Otter Premium: {tariff.title}"
    shp = None

    payment = Payment.objects.create(
        user=user,
        tariff=tariff,
        invoice_id=invoice_id,
        amount=Decimal(tariff.price),
        currency=tariff.currency,
        kind=kind,
        status=Payment.Status.PENDING,
        description=description,
        channel=channel,
    )

    sub = get_or_create_subscription(user)
    sub.tariff = tariff
    sub.recurring_enabled = use_robokassa_recurring
    sub.save(update_fields=["tariff", "recurring_enabled", "updated_at"])

    return payment, use_robokassa_recurring


@transaction.atomic
def create_checkout_payment(
    *,
    user,
    tariff: Tariff,
    recurring_consent: bool = False,
    offer_version: str = "",
    ip_address: str | None = None,
    user_agent: str = "",
) -> Payment:
    payment, use_robokassa_recurring = _prepare_checkout_payment(
        user=user,
        tariff=tariff,
        recurring_consent=recurring_consent,
        offer_version=offer_version,
        ip_address=ip_address,
        user_agent=user_agent,
        channel=Payment.Channel.WEB,
    )
    shp = None
    checkout_url = robokassa.build_checkout_url(
        out_sum=payment.amount,
        invoice_id=payment.invoice_id,
        description=payment.description,
        tariff=tariff,
        recurring=use_robokassa_recurring,
        user_email=getattr(user, "email", None),
        shp=shp,
    )
    payment.checkout_url = checkout_url
    payment.save(update_fields=["checkout_url", "updated_at"])
    return payment


@transaction.atomic
def create_mobile_sdk_payment(
    *,
    user,
    tariff: Tariff,
    recurring_consent: bool = False,
    offer_version: str = "",
    ip_address: str | None = None,
    user_agent: str = "",
) -> tuple[Payment, dict]:
    """Платёж для Robokassa Mobile SDK — параметры + подпись, без checkout_url."""
    payment, use_robokassa_recurring = _prepare_checkout_payment(
        user=user,
        tariff=tariff,
        recurring_consent=recurring_consent,
        offer_version=offer_version,
        ip_address=ip_address,
        user_agent=user_agent,
        channel=Payment.Channel.MOBILE_SDK,
    )
    sdk_params = robokassa.build_sdk_params(
        out_sum=payment.amount,
        invoice_id=payment.invoice_id,
        description=payment.description,
        tariff=tariff,
        recurring=use_robokassa_recurring,
        user_email=getattr(user, "email", None),
        shp=None,
    )
    return payment, sdk_params


@transaction.atomic
def apply_successful_payment(payment: Payment, raw: dict | None = None) -> Subscription:
    now = timezone.now()
    if payment.status == Payment.Status.PAID:
        return get_or_create_subscription(payment.user)

    payment.status = Payment.Status.PAID
    payment.paid_at = now
    if raw is not None:
        payment.raw_result = raw
    payment.save(update_fields=["status", "paid_at", "raw_result", "updated_at"])

    tariff = payment.tariff
    sub = get_or_create_subscription(payment.user)
    sub.tariff = tariff
    sub.status = Subscription.Status.ACTIVE
    sub.cancelled_at = None
    sub.promo_until = None

    if payment.kind in {Payment.Kind.INITIAL, Payment.Kind.ONE_TIME} and tariff.is_recurring:
        sub.parent_invoice_id = payment.invoice_id
        # Автосписание только если Robokassa recurring реально включён.
        sub.recurring_enabled = bool(robokassa.recurring_enabled())

    if tariff.duration_days == 0:
        sub.premium_until = None
    else:
        base = now
        if payment.kind == Payment.Kind.RECURRING and sub.premium_until and sub.premium_until > now:
            base = sub.premium_until
        sub.premium_until = base + timedelta(days=tariff.duration_days)

    sub.save()

    sync_app_settings_premium(
        payment.user,
        is_premium=True,
        premium_until=sub.premium_until,
        activated_at=now,
    )
    return sub


def cancel_subscription(user) -> Subscription:
    sub = get_or_create_subscription(user)
    sub.recurring_enabled = False
    sub.cancelled_at = timezone.now()
    if sub.status == Subscription.Status.ACTIVE:
        sub.status = Subscription.Status.CANCELLED
    sub.save(update_fields=["recurring_enabled", "cancelled_at", "status", "updated_at"])

    RecurringConsent.objects.filter(user=user, is_active=True).update(
        is_active=False,
        revoked_at=timezone.now(),
    )
    return sub


@transaction.atomic
def create_recurring_charge(subscription: Subscription) -> Payment | None:
    if not robokassa.recurring_enabled():
        return None
    if not subscription.recurring_enabled or not subscription.parent_invoice_id or not subscription.tariff:
        return None
    tariff = subscription.tariff
    invoice_id = _next_invoice_id()
    description = f"Otter Premium (авто): {tariff.title}"
    shp = {"Shp_user": str(subscription.user_id), "Shp_tariff": tariff.code}
    payment = Payment.objects.create(
        user=subscription.user,
        tariff=tariff,
        invoice_id=invoice_id,
        previous_invoice_id=subscription.parent_invoice_id,
        amount=Decimal(tariff.price),
        currency=tariff.currency,
        kind=Payment.Kind.RECURRING,
        status=Payment.Status.PENDING,
        description=description,
    )
    ok, body = robokassa.charge_recurring(
        out_sum=payment.amount,
        invoice_id=invoice_id,
        previous_invoice_id=subscription.parent_invoice_id,
        description=description,
        tariff=tariff,
        shp=shp,
    )
    payment.raw_result = {"recurring_response": body}
    if not ok:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status", "raw_result", "updated_at"])
        subscription.status = Subscription.Status.PAST_DUE
        subscription.save(update_fields=["status", "updated_at"])
        return payment
    payment.save(update_fields=["raw_result", "updated_at"])
    return payment


def refresh_expired_subscriptions() -> dict:
    """Промо/премиум истёк — обновляем статусы и инициируем recurring."""
    now = timezone.now()
    stats = {"trial_ended": 0, "expired": 0, "recurring_queued": 0}
    days_before = int(getattr(settings, "ROBOKASSA_RECURRING_DAYS_BEFORE", 1))

    for sub in Subscription.objects.filter(status=Subscription.Status.TRIAL, promo_until__lte=now):
        sub.status = Subscription.Status.PAST_DUE
        sub.save(update_fields=["status", "updated_at"])
        sync_app_settings_premium(sub.user, is_premium=False, premium_until=sub.promo_until)
        stats["trial_ended"] += 1

    for sub in Subscription.objects.filter(
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.CANCELLED],
        premium_until__lte=now,
    ):
        if sub.premium_until is None:
            continue
        if sub.recurring_enabled and sub.parent_invoice_id and sub.status == Subscription.Status.ACTIVE:
            payment = create_recurring_charge(sub)
            if payment:
                stats["recurring_queued"] += 1
            continue
        sub.status = Subscription.Status.EXPIRED
        sub.save(update_fields=["status", "updated_at"])
        sync_app_settings_premium(sub.user, is_premium=False, premium_until=sub.premium_until)
        stats["expired"] += 1

    horizon = now + timedelta(days=days_before)
    for sub in Subscription.objects.filter(
        status=Subscription.Status.ACTIVE,
        recurring_enabled=True,
        parent_invoice_id__isnull=False,
        premium_until__lte=horizon,
        premium_until__gt=now,
    ):
        exists = Payment.objects.filter(
            user=sub.user,
            kind=Payment.Kind.RECURRING,
            status=Payment.Status.PENDING,
            created_at__gte=now - timedelta(days=1),
        ).exists()
        if exists:
            continue
        payment = create_recurring_charge(sub)
        if payment:
            stats["recurring_queued"] += 1

    return stats
