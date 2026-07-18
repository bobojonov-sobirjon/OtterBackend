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
            "channel",
            "checkout_url",
            "paid_at",
            "created_at",
        )


class RobokassaSdkParamsSerializer(serializers.Serializer):
    merchant_login = serializers.CharField()
    invoice_id = serializers.IntegerField()
    out_sum = serializers.CharField()
    description = serializers.CharField()
    signature_value = serializers.CharField()
    culture = serializers.CharField()
    encoding = serializers.CharField()
    is_test = serializers.BooleanField()
    is_recurring = serializers.BooleanField()
    email = serializers.EmailField(required=False, allow_blank=True)
    receipt_json = serializers.CharField(required=False, allow_null=True)
    receipt = serializers.JSONField(required=False, allow_null=True)
    shp = serializers.DictField(child=serializers.CharField(), required=False, allow_null=True)


class MobileCheckoutResponseSerializer(serializers.Serializer):
    provider = serializers.CharField()
    payment = PaymentSerializer()
    sdk = RobokassaSdkParamsSerializer()
