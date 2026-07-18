from django.urls import path

from .mobile_views import (
    MobileLatestPendingPaymentAPIView,
    MobilePaymentStatusAPIView,
    MobilePremiumCancelAPIView,
    MobilePremiumCheckoutAPIView,
    MobilePremiumFeaturesAPIView,
    MobilePremiumTrialAPIView,
    MobileSubscriptionStatusAPIView,
    MobileTariffListAPIView,
)

urlpatterns = [
    path("premium/tariffs/", MobileTariffListAPIView.as_view(), name="mobile-premium-tariffs"),
    path("premium/subscription/", MobileSubscriptionStatusAPIView.as_view(), name="mobile-premium-subscription"),
    path("premium/checkout/", MobilePremiumCheckoutAPIView.as_view(), name="mobile-premium-checkout"),
    path("premium/trial/", MobilePremiumTrialAPIView.as_view(), name="mobile-premium-trial"),
    path("premium/cancel/", MobilePremiumCancelAPIView.as_view(), name="mobile-premium-cancel"),
    path("premium/features/", MobilePremiumFeaturesAPIView.as_view(), name="mobile-premium-features"),
    path(
        "premium/payments/<int:invoice_id>/",
        MobilePaymentStatusAPIView.as_view(),
        name="mobile-premium-payment-status",
    ),
    path(
        "premium/payments/pending/",
        MobileLatestPendingPaymentAPIView.as_view(),
        name="mobile-premium-payment-pending",
    ),
]
