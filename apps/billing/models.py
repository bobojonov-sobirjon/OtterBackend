from django.conf import settings
from django.db import models
from django.utils import timezone


class Tariff(models.Model):
    """Каталог тарифов подписки (цены и сроки хранятся у нас, не в Robokassa)."""

    code = models.SlugField("Код", max_length=40, unique=True)
    title = models.CharField("Название", max_length=150)
    description = models.TextField("Описание", blank=True, default="")
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2)
    currency = models.CharField("Валюта", max_length=3, default="RUB")
    duration_days = models.PositiveIntegerField(
        "Длительность (дней)",
        help_text="Сколько дней премиума даёт оплата. 0 = бессрочно.",
    )
    promo_days = models.PositiveIntegerField(
        "Промо-период (дней)",
        default=0,
        help_text="Бесплатный период на нашей стороне (Robokassa промо не даёт).",
    )
    is_recurring = models.BooleanField(
        "Рекуррентный",
        default=True,
        help_text="Автосписание через Robokassa Recurring API.",
    )
    receipt_name = models.CharField(
        "Название в чеке",
        max_length=128,
        help_text="Номенклатура для фискализации Robokassa.",
    )
    vat = models.CharField(
        "НДС",
        max_length=16,
        default="none",
        help_text="none | vat0 | vat10 | vat20 | vat110 | vat120",
    )
    payment_object = models.CharField("Предмет расчёта", max_length=32, default="service")
    payment_method = models.CharField("Способ расчёта", max_length=32, default="full_payment")
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Тариф"
        verbose_name_plural = "1. Тарифы"
        ordering = ("sort_order", "price")

    def __str__(self) -> str:
        return f"{self.title} ({self.code})"


class Subscription(models.Model):
    class Status(models.TextChoices):
        NONE = "none", "Нет"
        TRIAL = "trial", "Промо-период"
        ACTIVE = "active", "Активна"
        PAST_DUE = "past_due", "Просрочена оплата"
        CANCELLED = "cancelled", "Отменена"
        EXPIRED = "expired", "Истекла"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
        verbose_name="Пользователь",
    )
    tariff = models.ForeignKey(
        Tariff,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        verbose_name="Тариф",
        null=True,
        blank=True,
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.NONE,
    )
    promo_until = models.DateTimeField("Промо до", blank=True, null=True)
    premium_until = models.DateTimeField("Премиум до", blank=True, null=True)
    recurring_enabled = models.BooleanField("Автосписание включено", default=False)
    parent_invoice_id = models.PositiveBigIntegerField(
        "InvId материнского платежа",
        blank=True,
        null=True,
        help_text="Нужен для дочерних recurring-списаний.",
    )
    cancelled_at = models.DateTimeField("Отменено", blank=True, null=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Подписка"
        verbose_name_plural = "2. Подписки"

    def __str__(self) -> str:
        return f"subscription::{self.user_id}::{self.status}"

    @property
    def is_premium_now(self) -> bool:
        now = timezone.now()
        if self.status == self.Status.TRIAL and self.promo_until and self.promo_until > now:
            return True
        if self.status in {self.Status.ACTIVE, self.Status.CANCELLED}:
            if self.premium_until is None:
                # lifetime / бессрочно после оплаты
                return self.status == self.Status.ACTIVE
            return self.premium_until > now
        return False


class RecurringConsent(models.Model):
    """История согласий на автосписания (требование Robokassa)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recurring_consents",
        verbose_name="Пользователь",
    )
    tariff = models.ForeignKey(
        Tariff,
        on_delete=models.PROTECT,
        related_name="consents",
        verbose_name="Тариф",
    )
    offer_version = models.CharField("Версия оферты", max_length=64, blank=True, default="")
    agreed = models.BooleanField("Согласие", default=True)
    ip_address = models.GenericIPAddressField("IP", blank=True, null=True)
    user_agent = models.TextField("User-Agent", blank=True, default="")
    is_active = models.BooleanField("Актуально", default=True)
    agreed_at = models.DateTimeField("Дата согласия", auto_now_add=True)
    revoked_at = models.DateTimeField("Отозвано", blank=True, null=True)

    class Meta:
        verbose_name = "Согласие на автосписание"
        verbose_name_plural = "3. Согласия на автосписание"
        ordering = ("-agreed_at",)

    def __str__(self) -> str:
        return f"consent::{self.user_id}::{self.tariff_id}"


class Payment(models.Model):
    class Kind(models.TextChoices):
        INITIAL = "initial", "Первый / материнский"
        RECURRING = "recurring", "Дочерний (recurring)"
        ONE_TIME = "one_time", "Разовый"

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает оплаты"
        PAID = "paid", "Оплачен"
        FAILED = "failed", "Ошибка"
        CANCELLED = "cancelled", "Отменён"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="Пользователь",
    )
    tariff = models.ForeignKey(
        Tariff,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name="Тариф",
    )
    invoice_id = models.PositiveBigIntegerField("InvId", unique=True)
    previous_invoice_id = models.PositiveBigIntegerField(
        "PreviousInvoiceID",
        blank=True,
        null=True,
    )
    amount = models.DecimalField("Сумма", max_digits=10, decimal_places=2)
    currency = models.CharField("Валюта", max_length=3, default="RUB")
    kind = models.CharField("Тип", max_length=20, choices=Kind.choices, default=Kind.INITIAL)
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    description = models.CharField("Описание", max_length=255, blank=True, default="")
    checkout_url = models.TextField("Checkout URL", blank=True, default="")
    raw_result = models.JSONField("Ответ Robokassa", default=dict, blank=True)
    paid_at = models.DateTimeField("Оплачено", blank=True, null=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Платёж"
        verbose_name_plural = "4. Платежи"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"payment::{self.invoice_id}::{self.status}"
