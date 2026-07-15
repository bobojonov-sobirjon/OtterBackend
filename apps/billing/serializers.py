from rest_framework import serializers

from .models import Payment, Subscription, Tariff


class TariffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tariff
        fields = (
            "code",
            "title",
            "description",
            "price",
            "currency",
            "duration_days",
            "promo_days",
            "is_recurring",
            "sort_order",
        )


class SubscriptionSerializer(serializers.ModelSerializer):
    tariff = TariffSerializer(read_only=True)
    is_premium = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = (
            "status",
            "tariff",
            "promo_until",
            "premium_until",
            "recurring_enabled",
            "cancelled_at",
            "is_premium",
            "updated_at",
        )

    def get_is_premium(self, obj: Subscription) -> bool:
        return obj.is_premium_now


class PremiumCheckoutSerializer(serializers.Serializer):
    tariff = serializers.SlugField()
    recurring_consent = serializers.BooleanField(required=False, default=False)
    offer_version = serializers.CharField(required=False, allow_blank=True, default="")


class PremiumTrialSerializer(serializers.Serializer):
    tariff = serializers.SlugField()
    recurring_consent = serializers.BooleanField(required=False, default=False)
    offer_version = serializers.CharField(required=False, allow_blank=True, default="")


class PaymentSerializer(serializers.ModelSerializer):
    tariff = serializers.SlugRelatedField(slug_field="code", read_only=True)

    class Meta:
        model = Payment
        fields = (
            "invoice_id",
            "tariff",
            "amount",
            "currency",
            "kind",
            "status",
            "checkout_url",
            "paid_at",
            "created_at",
        )
