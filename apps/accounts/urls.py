from django.urls import path

from .views import (
    GoogleLoginAPIView,
    TokenRefreshAPIView,
    ВходAPIView,
    ЗабылиПарольНовыйПарольAPIView,
    ЗабылиПарольЗапросAPIView,
    ЗабылиПарольПроверкаКодаAPIView,
    ПрофильAPIView,
    РегистрацияAPIView,
)


urlpatterns = [
    # Auth
    path("auth/register/", РегистрацияAPIView.as_view(), name="register"),
    path("auth/login/", ВходAPIView.as_view(), name="login"),
    path("auth/google/", GoogleLoginAPIView.as_view(), name="google-login"),
    path("auth/token/refresh/", TokenRefreshAPIView.as_view(), name="token-refresh"),
    # Forgot password
    path("auth/forgot-password/", ЗабылиПарольЗапросAPIView.as_view(), name="forgot-password"),
    path("auth/forgot-password/verify/", ЗабылиПарольПроверкаКодаAPIView.as_view(), name="forgot-password-verify"),
    path("auth/forgot-password/confirm/", ЗабылиПарольНовыйПарольAPIView.as_view(), name="forgot-password-confirm"),
    # Profile
    path("profile/", ПрофильAPIView.as_view(), name="profile"),
]

