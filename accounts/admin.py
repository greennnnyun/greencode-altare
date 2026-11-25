from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import EmailOTP, Profile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'role', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('email', 'username', 'profile__nickname')
    ordering = ('-date_joined',)
    fieldsets = BaseUserAdmin.fieldsets + (
        ('蛋壳栖所身份', {'fields': ('role', 'login_failures', 'locked_until')}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('email', 'password1', 'password2', 'role')}),
    )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'nickname', 'phone', 'verified')
    list_filter = ('verified',)
    search_fields = ('user__email', 'nickname', 'phone')


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'code', 'purpose', 'used', 'attempts', 'expires_at', 'created_at')
    list_filter = ('purpose', 'used')
    search_fields = ('email',)
    readonly_fields = ('created_at',)
