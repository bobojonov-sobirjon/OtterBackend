from django.contrib import admin

from .models import Payment, RecurringConsent, Subscription, Tariff


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "title",
        "price",
        "currency",
        "duration_days",
        "promo_days",
        "is_recurring",
        "is_active",
        "sort_order",
    )
    list_filter = ("is_active", "is_recurring", "currency")
    search_fields = ("code", "title", "receipt_name")
    # code задаётся вручную (monthly / yearly), не из русского title



@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "tariff",
        "status",
        "promo_until",
        "premium_until",
        "recurring_enabled",
        "parent_invoice_id",
    )
    list_filter = ("status", "recurring_enabled")
    search_fields = ("user__email",)
    raw_id_fields = ("user", "tariff")


@admin.register(RecurringConsent)
class RecurringConsentAdmin(admin.ModelAdmin):
    list_display = ("user", "tariff", "agreed", "is_active", "agreed_at", "ip_address")
    list_filter = ("is_active", "agreed")
    search_fields = ("user__email", "offer_version")
    raw_id_fields = ("user", "tariff")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_id",
        "user",
        "tariff",
        "amount",
        "kind",
        "status",
        "paid_at",
        "created_at",
    )
    list_filter = ("status", "kind")
    search_fields = ("invoice_id", "user__email")
    raw_id_fields = ("user", "tariff")
    readonly_fields = ("checkout_url", "raw_result", "created_at", "updated_at")
