import uuid
from decimal import Decimal
from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone


class BusinessSettings(models.Model):
    """
    Singleton-style global settings for Rayara Cafe.
    """
    cafe_name = models.CharField(max_length=100, default='Rayara Cafe')
    tagline = models.CharField(max_length=150, default='Good food. Great moments.')
    address = models.TextField(default='Rayara Cafe, Main Road, Calicut')
    phone = models.CharField(max_length=20, default='+91 98765 43210')
    gst_number = models.CharField(max_length=30, blank=True)
    fssai_license = models.CharField(max_length=30, blank=True)
    currency_symbol = models.CharField(max_length=5, default='₹')
    receipt_footer_text = models.TextField(
        default='Thank you for visiting Rayara Cafe!\nFreshly made · Warmly served'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Business Settings'
        verbose_name_plural = 'Business Settings'

    def __str__(self):
        return self.cafe_name

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class DiningTable(models.Model):
    """
    Restaurant tables for dine-in orders.
    """
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('reserved', 'Reserved'),
    ]
    number = models.CharField(max_length=20, unique=True, help_text='e.g. T1, T2, Table 5')
    capacity = models.PositiveIntegerField(default=4)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['number']
        verbose_name = 'Dining Table'
        verbose_name_plural = 'Dining Tables'

    def __str__(self):
        return f"Table {self.number} ({self.get_status_display()})"

    def get_active_order(self):
        """Returns the currently active unpaid dine-in order for this table, if any."""
        return self.orders.filter(
            order_type='dine_in',
            is_paid=False
        ).exclude(status='cancelled').first()


class Category(models.Model):
    """
    Food menu categories (Shawarma, Grills, Beverages, etc.)
    """
    name = models.CharField(max_length=100, unique=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'Menu Category'
        verbose_name_plural = 'Menu Categories'

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Food items with price, availability and soft-deletion capability.
    """
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    is_available = models.BooleanField(default=True, help_text='Toggle when out of stock')
    is_active = models.BooleanField(default=True, help_text='Soft-delete flag')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category__display_order', 'name']
        verbose_name = 'Food Product'
        verbose_name_plural = 'Food Products'

    def __str__(self):
        status = "Available" if self.is_available else "Out of Stock"
        return f"{self.name} - ₹{self.price} ({status})"


class TaxConfiguration(models.Model):
    """
    Configurable legal taxes (CGST, SGST, VAT) editable by owner.
    """
    name = models.CharField(max_length=50, help_text='e.g. CGST 2.5%, SGST 2.5%')
    rate_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('2.50'))
    is_inclusive = models.BooleanField(
        default=False,
        help_text='If true, tax is included in menu price. If false, added at bill time.'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tax Configuration'
        verbose_name_plural = 'Tax Configurations'

    def __str__(self):
        return f"{self.name} ({self.rate_percentage}%)"


class Discount(models.Model):
    """
    Configurable restaurant discounts.
    """
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage (%)'),
        ('fixed', 'Fixed Amount (₹)'),
    ]
    name = models.CharField(max_length=100)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='percentage')
    value = models.DecimalField(max_digits=10, decimal_places=2)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Discount'
        verbose_name_plural = 'Discounts'

    def __str__(self):
        unit = "%" if self.discount_type == 'percentage' else "₹"
        return f"{self.name} ({self.value}{unit})"


class Order(models.Model):
    """
    Central Order entity supporting Dine-In and Takeaway with transaction safety.
    """
    ORDER_TYPE_CHOICES = [
        ('dine_in', 'Dine-In'),
        ('takeaway', 'Takeaway'),
    ]
    STATUS_CHOICES = [
        ('new', 'New'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    order_number = models.CharField(max_length=32, unique=True, db_index=True)
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, default='dine_in')
    table = models.ForeignKey(
        DiningTable,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='orders'
    )
    customer = models.ForeignKey(
        'core.Customer',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='pos_orders'
    )
    coupon = models.ForeignKey(
        'core.Coupon',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='pos_orders'
    )
    coupon_code = models.CharField(max_length=32, blank=True)
    customer_name = models.CharField(max_length=100, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    takeaway_notes = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_orders')

    # Financial snapshots (All computed server-side, never trusted from client)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    is_paid = models.BooleanField(default=False, db_index=True)
    current_batch = models.PositiveIntegerField(default=1, help_text='Increments with each additional order batch')

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'

    def __str__(self):
        target = f"Table {self.table.number}" if self.order_type == 'dine_in' and self.table else "Takeaway"
        return f"{self.order_number} ({target}) - ₹{self.grand_total} [{self.get_status_display()}]"

    @classmethod
    def generate_next_order_number(cls, order_type='dine_in'):
        """
        Generates clean human-readable sequential order numbers.
        e.g. D-0101 for Dine-in or T-0101 for Takeaway.
        Includes collision-prevention loop for multi-staff concurrent order submission.
        """
        prefix = "D" if order_type == 'dine_in' else "T"
        today = timezone.now().strftime('%y%m%d')
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        count = cls.objects.filter(created_at__gte=today_start).count() + 1
        candidate = f"{prefix}-{today}-{count:03d}"
        while cls.objects.filter(order_number=candidate).exists():
            count += 1
            candidate = f"{prefix}-{today}-{count:03d}"
        return candidate

    def recalculate_totals(self, apply_discount_amount=Decimal('0.00')):
        """
        Recomputes subtotal, taxes and grand total server-side based on uncancelled items.
        """
        active_items = self.items.filter(is_cancelled=False)
        self.subtotal = sum((item.line_total for item in active_items), Decimal('0.00'))
        self.discount_amount = min(Decimal(str(apply_discount_amount)), self.subtotal)

        taxable_amount = max(Decimal('0.00'), self.subtotal - self.discount_amount)
        active_taxes = TaxConfiguration.objects.filter(is_active=True, is_inclusive=False)
        total_tax_rate = sum((t.rate_percentage for t in active_taxes), Decimal('0.00'))
        self.tax_amount = (taxable_amount * (total_tax_rate / Decimal('100.00'))).quantize(Decimal('0.01'))

        self.grand_total = (taxable_amount + self.tax_amount).quantize(Decimal('0.01'))
        self.save(update_fields=['subtotal', 'discount_amount', 'tax_amount', 'grand_total'])
        return self.grand_total


class OrderItem(models.Model):
    """
    Individual food line items with historical price snapshots and batch tracking.
    """
    STATUS_CHOICES = [
        ('ordered', 'Ordered'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready'),
        ('served', 'Served'),
        ('cancelled', 'Cancelled'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        Product,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='order_items'
    )
    product_name = models.CharField(max_length=150, help_text='Historical snapshot at order time')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Historical snapshot')
    quantity = models.PositiveIntegerField(default=1)
    special_instructions = models.CharField(max_length=255, blank=True)
    batch_number = models.PositiveIntegerField(
        default=1,
        help_text='1 for initial order, 2+ for additional items added later'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ordered')
    is_kitchen_printed = models.BooleanField(default=False)
    is_cancelled = models.BooleanField(default=False, db_index=True)
    cancellation_reason = models.CharField(max_length=255, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cancelled_items'
    )

    line_total = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['batch_number', 'id']
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'

    def __str__(self):
        cancelled_tag = " [CANCELLED]" if self.is_cancelled else ""
        return f"{self.quantity}x {self.product_name} (₹{self.line_total}){cancelled_tag}"

    def save(self, *args, **kwargs):
        self.line_total = (Decimal(str(self.unit_price)) * Decimal(str(self.quantity))).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)


class PrinterConfiguration(models.Model):
    """
    Configurable thermal printer setups for kitchen and billing counter.
    Supports TVS USB drivers, Ethernet RAW sockets, and simulated testing mode.
    """
    PRINTER_TYPE_CHOICES = [
        ('kitchen', 'Kitchen Thermal Printer'),
        ('billing', 'Billing Counter Printer'),
    ]
    CONNECTION_TYPE_CHOICES = [
        ('simulated', 'Simulated / Virtual (Development & Testing)'),
        ('usb_spooler', 'USB / Windows Spooler Driver (e.g. TVS RP 3160)'),
        ('ethernet', 'Ethernet / Wi-Fi Network RAW Socket (Port 9100)'),
        ('serial', 'Serial COM Port'),
    ]

    printer_type = models.CharField(max_length=20, choices=PRINTER_TYPE_CHOICES, unique=True)
    name = models.CharField(max_length=100, default='TVS Thermal Printer')
    connection_type = models.CharField(
        max_length=20,
        choices=CONNECTION_TYPE_CHOICES,
        default='simulated'
    )
    device_identifier = models.CharField(
        max_length=255,
        default='virtual',
        help_text='Windows Printer Driver Name (for USB) or IP Address (for Ethernet)'
    )
    port = models.PositiveIntegerField(default=9100, help_text='Default 9100 for network thermal printers')
    paper_width_mm = models.PositiveIntegerField(default=80, help_text='Standard 80mm or 58mm roll')
    characters_per_line = models.PositiveIntegerField(default=42, help_text='42 for 80mm font A, 32 for 58mm')
    auto_cut = models.BooleanField(default=True)
    open_cash_drawer = models.BooleanField(default=False, help_text='Pulse cash drawer on bill print')
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Printer Configuration'
        verbose_name_plural = 'Printer Configurations'

    def __str__(self):
        return f"{self.get_printer_type_display()} [{self.get_connection_type_display()}: {self.device_identifier}]"


class PrintJob(models.Model):
    """
    Persistent, idempotent print jobs with worker locking and retry counts.
    """
    PRINTER_TYPE_CHOICES = [
        ('kitchen', 'Kitchen'),
        ('billing', 'Billing'),
    ]
    JOB_TYPE_CHOICES = [
        ('new_order', 'New Kitchen Order'),
        ('additional_order', 'Additional Kitchen Items'),
        ('cancelled_item', 'Cancelled Kitchen Items Ticket'),
        ('reprint_kitchen', 'Reprint Kitchen Order'),
        ('guest_bill', 'Guest Table Bill / Estimate'),
        ('bill_receipt', 'Customer Bill Receipt'),
        ('reprint_bill', 'Reprint Customer Bill'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('printed', 'Printed'),
        ('failed', 'Failed'),
    ]

    idempotency_key = models.CharField(max_length=100, unique=True, db_index=True)
    printer_type = models.CharField(max_length=20, choices=PRINTER_TYPE_CHOICES)
    job_type = models.CharField(max_length=30, choices=JOB_TYPE_CHOICES)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='print_jobs')

    content = models.TextField(help_text='Formatted ticket payload or preview text')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)

    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.CharField(max_length=100, blank=True)
    printed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Print Job'
        verbose_name_plural = 'Print Jobs'

    def __str__(self):
        return f"Job #{self.id} [{self.get_job_type_display()}] for {self.order.order_number} ({self.status})"


class Payment(models.Model):
    """
    Financial payment record preventing duplicate billing.
    """
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('upi', 'UPI / QR'),
        ('card', 'Credit/Debit Card'),
    ]
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    reference_number = models.CharField(max_length=100, blank=True, help_text='UPI UTR or card transaction ID')
    received_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        return f"₹{self.amount} via {self.get_payment_method_display()} for {self.order.order_number}"


class Receipt(models.Model):
    """
    Immutable customer billing receipt record with reprint tracking.
    """
    receipt_number = models.CharField(max_length=32, unique=True, db_index=True)
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name='receipt')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20)
    issued_by = models.ForeignKey(User, on_delete=models.PROTECT)
    issued_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_reprint = models.BooleanField(default=False)
    reprint_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-issued_at']
        verbose_name = 'Customer Receipt'
        verbose_name_plural = 'Customer Receipts'

    def __str__(self):
        return f"Receipt #{self.receipt_number} (Order: {self.order.order_number}) - ₹{self.grand_total}"

    @classmethod
    def generate_next_receipt_number(cls):
        """
        Generates sequential receipt numbers with concurrency collision protection.
        """
        today = timezone.now().strftime('%y%m%d')
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        count = cls.objects.filter(issued_at__gte=today_start).count() + 1
        candidate = f"RCP-{today}-{count:04d}"
        while cls.objects.filter(receipt_number=candidate).exists():
            count += 1
            candidate = f"RCP-{today}-{count:04d}"
        return candidate


class AuditLog(models.Model):
    """
    System activity and security audit trail.
    """
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=50, db_index=True)
    entity_type = models.CharField(max_length=50)
    entity_id = models.CharField(max_length=50)
    details = models.TextField(help_text='JSON formatted audit description')
    ip_address = models.CharField(max_length=45, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'

    def __str__(self):
        actor = self.user.username if self.user else "System"
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {actor} -> {self.action} ({self.entity_type} #{self.entity_id})"
