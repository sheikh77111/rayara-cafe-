from django.contrib import admin
from .models import (
    MenuCategory, MenuItem, Game, Reward, GuestSession,
    GameAttempt, Coupon, Redemption, AuditLog, Customer, CustomerOTP
)

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('email', 'created_at', 'last_login', 'is_active')
    search_fields = ('email', 'phone_number')

@admin.register(CustomerOTP)
class CustomerOTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'otp_code', 'created_at', 'expires_at', 'is_verified', 'attempts')
    search_fields = ('email',)

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code_hint', 'email', 'percentage', 'status', 'valid_from', 'expires_at', 'issued_at')
    list_filter = ('status', 'percentage')
    search_fields = ('code_hint', 'email', 'phone_number')

@admin.register(GameAttempt)
class GameAttemptAdmin(admin.ModelAdmin):
    list_display = ('email', 'game', 'reward', 'created_at')
    search_fields = ('email', 'phone_number')

admin.site.register([MenuCategory, MenuItem, Game, Reward, GuestSession, Redemption, AuditLog])
