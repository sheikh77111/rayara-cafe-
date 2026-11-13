from rest_framework import serializers
from .models import MenuCategory, MenuItem, Coupon, Customer

class MenuItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    class Meta:
        model = MenuItem
        fields = ['id', 'name', 'description', 'price', 'image_url', 'available', 'category_name']

class MenuCategorySerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    class Meta:
        model = MenuCategory
        fields = ['id', 'name', 'items']
    def get_items(self, obj):
        return MenuItemSerializer(obj.items.filter(available=True), many=True).data

class CouponSerializer(serializers.ModelSerializer):
    code = serializers.SerializerMethodField()
    customer_email = serializers.CharField(source='email', read_only=True)
    customer_phone = serializers.CharField(source='phone_number', read_only=True)

    class Meta:
        model = Coupon
        fields = ['id', 'code', 'customer_email', 'customer_phone', 'percentage', 'minimum_spend', 'max_discount', 'issued_at', 'valid_from', 'expires_at', 'status']

    def get_code(self, obj):
        return obj.code_plain if getattr(obj, 'code_plain', None) else f"RAYA-*{obj.code_hint}"

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'email', 'phone_number', 'created_at', 'last_login']
