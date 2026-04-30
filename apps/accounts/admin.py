from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from .models import CustomUser, PasswordResetRequest


class UserTypeFilter(admin.SimpleListFilter):
    title = "Тип пользователя"
    parameter_name = "user_type"

    def lookups(self, request, model_admin):
        return (
            ("superuser", "Суперпользователь"),
            ("regular", "Обычный пользователь"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "superuser":
            return queryset.filter(is_superuser=True)
        if value == "regular":
            return queryset.filter(is_superuser=False)
        return queryset


class PasswordResetRequestInline(admin.TabularInline):
    model = PasswordResetRequest
    extra = 0
    fields = ("email", "code", "reset_token", "expires_at", "used_at", "created_at")
    readonly_fields = ("reset_token", "created_at")
    ordering = ("-created_at",)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("email", "first_name", "last_name", "is_active", "is_staff", "date_joined")
    list_filter = (UserTypeFilter, "is_active", "is_staff")
    ordering = ("-date_joined",)
    search_fields = ("email", "first_name", "last_name")
    inlines = [PasswordResetRequestInline]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Персональные данные", {"fields": ("first_name", "last_name", "avatar")}),
        ("Важные даты", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )


try:
    admin.site.unregister(BlacklistedToken)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(OutstandingToken)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(Site)
except admin.sites.NotRegistered:
    pass

