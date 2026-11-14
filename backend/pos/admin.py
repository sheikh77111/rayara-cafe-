from django.contrib import admin
from .models import (
    BusinessSettings, DiningTable, Category, Product,
    ProductOptionGroup, ProductOption,
    TaxConfiguration, Discount, Order, OrderItem,
    PrinterConfiguration, PrintJob, Payment, Receipt, AuditLog
)

class ProductOptionInline(admin.TabularInline):
    model = ProductOption
    extra = 1

@admin.register(ProductOptionGroup)
class ProductOptionGroupAdmin(admin.ModelAdmin):
    list_display = ('product', 'name', 'selection_type', 'is_required', 'display_order')
    list_filter = ('selection_type', 'is_required')
    search_fields = ('product__name', 'name')
    inlines = [ProductOptionInline]

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name', 'unit_price', 'line_total', 'batch_number', 'is_kitchen_printed')

class PrintJobInline(admin.TabularInline):
    model = PrintJob
    extra = 0
    readonly_fields = ('printer_type', 'job_type', 'status', 'attempts', 'created_at', 'printed_at')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'order_type', 'table', 'status', 'grand_total', 'is_paid', 'created_at')
    list_filter = ('order_type', 'status', 'is_paid', 'created_at')
    search_fields = ('order_number', 'customer_name', 'customer_phone', 'table__number')
    readonly_fields = ('order_number', 'subtotal', 'tax_amount', 'grand_total', 'created_at', 'updated_at')
    inlines = [OrderItemInline, PrintJobInline]

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'is_available', 'is_active')
    list_filter = ('category', 'is_available', 'is_active')
    search_fields = ('name', 'category__name')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_order', 'is_active')
    list_editable = ('display_order', 'is_active')

@admin.register(DiningTable)
class DiningTableAdmin(admin.ModelAdmin):
    list_display = ('number', 'capacity', 'status', 'is_active')
    list_filter = ('status', 'is_active')
    list_editable = ('status', 'is_active')

@admin.register(PrinterConfiguration)
class PrinterConfigurationAdmin(admin.ModelAdmin):
    list_display = ('printer_type', 'name', 'connection_type', 'device_identifier', 'port', 'is_active')
    list_filter = ('printer_type', 'connection_type', 'is_active')

@admin.register(PrintJob)
class PrintJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'printer_type', 'job_type', 'order', 'status', 'attempts', 'created_at', 'printed_at')
    list_filter = ('printer_type', 'job_type', 'status', 'created_at')
    search_fields = ('order__order_number', 'idempotency_key')
    readonly_fields = ('idempotency_key', 'created_at')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'amount', 'payment_method', 'reference_number', 'received_by', 'created_at')
    list_filter = ('payment_method', 'created_at')
    search_fields = ('order__order_number', 'reference_number')

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'order', 'grand_total', 'payment_method', 'is_reprint', 'issued_at')
    list_filter = ('payment_method', 'is_reprint', 'issued_at')
    search_fields = ('receipt_number', 'order__order_number')

@admin.register(TaxConfiguration)
class TaxConfigurationAdmin(admin.ModelAdmin):
    list_display = ('name', 'rate_percentage', 'is_inclusive', 'is_active')

@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ('name', 'discount_type', 'value', 'min_order_amount', 'is_active')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'entity_type', 'entity_id')
    list_filter = ('action', 'entity_type', 'timestamp')
    search_fields = ('entity_id', 'details')
    readonly_fields = ('timestamp', 'user', 'action', 'entity_type', 'entity_id', 'details', 'ip_address')

@admin.register(BusinessSettings)
class BusinessSettingsAdmin(admin.ModelAdmin):
    list_display = ('cafe_name', 'phone', 'gst_number', 'currency_symbol', 'updated_at')
