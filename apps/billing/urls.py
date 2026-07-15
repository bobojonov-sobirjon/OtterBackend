from django.urls import path

from .views import (
    PremiumActivateAPIView,
    PremiumCancelAPIView,
    PremiumCheckoutAPIView,
    PremiumFeaturesAPIView,
    PremiumTrialAPIView,
    RobokassaResultAPIView,
    SubscriptionStatusAPIView,
    TariffListAPIView,
)

urlpatterns = [
    path("premium/tariffs/", TariffListAPIView.as_view(), name="premium-tariffs"),
    path("premium/subscription/", SubscriptionStatusAPIView.as_view(), name="premium-subscription"),
    path("premium/checkout/", PremiumCheckoutAPIView.as_view(), name="premium-checkout"),
    path("premium/trial/", PremiumTrialAPIView.as_view(), name="premium-trial"),
    path("premium/cancel/", PremiumCancelAPIView.as_view(), name="premium-cancel"),
    path("premium/activate/", PremiumActivateAPIView.as_view(), name="premium-activate"),
    path("premium/features/", PremiumFeaturesAPIView.as_view(), name="premium-features"),
    path("premium/robokassa/result/", RobokassaResultAPIView.as_view(), name="robokassa-result"),
]
