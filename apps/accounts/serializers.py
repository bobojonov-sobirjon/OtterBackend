from django.contrib.auth import authenticate, password_validation
from rest_framework import serializers

from .models import CustomUser


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, label="Пароль")

    class Meta:
        model = CustomUser
        fields = ("email", "password", "first_name", "last_name")

    email = serializers.EmailField(label="Электронная почта")
    first_name = serializers.CharField(required=False, allow_blank=True, label="Имя")
    last_name = serializers.CharField(required=False, allow_blank=True, label="Фамилия")

    def validate(self, attrs):
        password = attrs.get("password")
        password_validation.validate_password(password)
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = CustomUser.objects.create_user(**validated_data, password=password)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(label="Электронная почта")
    password = serializers.CharField(write_only=True, label="Пароль")

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        user = authenticate(username=email, password=password)
        if not user:
            raise serializers.ValidationError({"detail": "Неверный email или пароль"})
        if not user.is_active:
            raise serializers.ValidationError({"detail": "Пользователь заблокирован"})
        attrs["user"] = user
        return attrs


class ProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(read_only=True, label="Электронная почта")
    first_name = serializers.CharField(required=False, allow_blank=True, label="Имя")
    last_name = serializers.CharField(required=False, allow_blank=True, label="Фамилия")
    avatar = serializers.ImageField(required=False, allow_null=True, label="Аватар")

    class Meta:
        model = CustomUser
        fields = ("id", "email", "first_name", "last_name", "avatar")


class ForgotPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(label="Электронная почта")


class ForgotPasswordVerifyCodeSerializer(serializers.Serializer):
    email = serializers.EmailField(label="Электронная почта")
    code = serializers.CharField(label="Код")


class ForgotPasswordConfirmSerializer(serializers.Serializer):
    reset_token = serializers.UUIDField(label="Токен сброса")
    new_password = serializers.CharField(write_only=True, min_length=8, label="Новый пароль")

    def validate(self, attrs):
        password_validation.validate_password(attrs["new_password"])
        return attrs


class GoogleLoginSerializer(serializers.Serializer):
    firebase_token = serializers.CharField(label="Firebase токен")

