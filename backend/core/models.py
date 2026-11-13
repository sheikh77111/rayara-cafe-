import uuid
from django.db import models
from django.contrib.auth.models import User

class Customer(models.Model):
    email = models.EmailField(unique=True, db_index=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True, db_index=True)
    session_token_hash = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.email

class CustomerOTP(models.Model):
    email = models.EmailField(db_index=True)
    phone_number = models.CharField(max_length=20, blank=True, db_index=True)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)

    def __str__(self):
        return f"{self.email} - {self.otp_code} ({'verified' if self.is_verified else 'pending'})"

class GuestSession(models.Model):
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

class MenuCategory(models.Model):
    name = models.CharField(max_length=80)
    sort_order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    def __str__(self): return self.name

class MenuItem(models.Model):
    category = models.ForeignKey(MenuCategory, on_delete=models.PROTECT, related_name='items')
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=240, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    image_url = models.URLField(blank=True)
    available = models.BooleanField(default=True)
    def __str__(self): return self.name

class Game(models.Model):
    key = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    active = models.BooleanField(default=True)
    def __str__(self): return self.name

class Reward(models.Model):
    percentage = models.PositiveSmallIntegerField()
    weight = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)
    max_discount = models.DecimalField(max_digits=8, decimal_places=2, default=50)
    minimum_spend = models.DecimalField(max_digits=8, decimal_places=2, default=199)
    def __str__(self): return f"{self.percentage}% (weight {self.weight})"

class GameAttempt(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, null=True, blank=True, related_name='game_attempts')
    email = models.EmailField(blank=True, db_index=True)
    phone_number = models.CharField(max_length=20, blank=True, db_index=True)
    guest = models.ForeignKey(GuestSession, on_delete=models.SET_NULL, null=True, blank=True)
    game = models.ForeignKey(Game, on_delete=models.PROTECT)
    reward = models.ForeignKey(Reward, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email or self.phone_number or 'Guest'} - {self.game.name} - {self.reward.percentage}% at {self.created_at}"

class Coupon(models.Model):
    STATUS = [('active', 'Active'), ('redeemed', 'Redeemed'), ('expired', 'Expired')]
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, null=True, blank=True, related_name='coupons')
    email = models.EmailField(blank=True, db_index=True)
    phone_number = models.CharField(max_length=20, blank=True, db_index=True)
    guest_session = models.ForeignKey(GuestSession, on_delete=models.SET_NULL, null=True, blank=True, related_name='coupons')
    code_hash = models.CharField(max_length=64, unique=True)
    code_hint = models.CharField(max_length=8)
    percentage = models.PositiveSmallIntegerField()
    minimum_spend = models.DecimalField(max_digits=8, decimal_places=2)
    max_discount = models.DecimalField(max_digits=8, decimal_places=2)
    issued_at = models.DateTimeField(auto_now_add=True)
    valid_from = models.DateTimeField()
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=STATUS, default='active')

    def __str__(self):
        return f"{self.code_hint} ({self.percentage}%) - {self.status}"

class Redemption(models.Model):
    coupon = models.OneToOneField(Coupon, on_delete=models.PROTECT)
    staff = models.ForeignKey(User, on_delete=models.PROTECT)
    bill_amount = models.DecimalField(max_digits=8, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2)
    redeemed_at = models.DateTimeField(auto_now_add=True)

class AuditLog(models.Model):
    actor = models.CharField(max_length=100)
    action = models.CharField(max_length=100)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
