from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from pos.models import (
    BusinessSettings, DiningTable, Category, Product,
    TaxConfiguration, Discount, PrinterConfiguration
)

class Command(BaseCommand):
    help = "Seeds initial configuration, dining tables, categories, menu items, and printers for Rayara Cafe POS"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding Rayara Cafe POS initial data..."))

        # 1. Business Settings
        settings = BusinessSettings.get_settings()
        settings.cafe_name = "Rayara Cafe"
        settings.tagline = "Good food. Great moments."
        settings.address = "Rayara Cafe, Beach Road, Calicut, Kerala"
        settings.phone = "+91 98765 43210"
        settings.gst_number = "32AAAAA0000A1Z5"
        settings.fssai_license = "11322000000001"
        settings.currency_symbol = "₹"
        settings.receipt_footer_text = "Thank you for dining at Rayara Cafe!\nFreshly made · Warmly served · Visit again"
        settings.save()
        self.stdout.write(self.style.SUCCESS("✓ Business Settings initialized"))

        # 2. Staff & Admin Accounts
        admin_user, created = User.objects.get_or_create(username="admin")
        if created or not admin_user.has_usable_password():
            admin_user.set_password("admin123")
            admin_user.is_superuser = True
            admin_user.is_staff = True
            admin_user.first_name = "Rayara"
            admin_user.last_name = "Owner"
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("✓ Admin user created: admin / admin123"))

        staff_user, created = User.objects.get_or_create(username="staff1")
        if created or not staff_user.has_usable_password():
            staff_user.set_password("staff123")
            staff_user.is_staff = True
            staff_user.is_superuser = False
            staff_user.first_name = "Counter"
            staff_user.last_name = "Staff"
            staff_user.save()
            self.stdout.write(self.style.SUCCESS("✓ Staff user created: staff1 / staff123"))

        # 3. Dining Tables (10 Tables)
        tables_data = [
            ("T1", 2), ("T2", 2), ("T3", 4), ("T4", 4),
            ("T5", 4), ("T6", 6), ("T7", 6), ("T8", 8),
            ("T9", 4), ("T10", 4)
        ]
        for num, cap in tables_data:
            DiningTable.objects.get_or_create(
                number=num,
                defaults={'capacity': cap, 'status': 'available', 'is_active': True}
            )
        self.stdout.write(self.style.SUCCESS(f"✓ Seeded {len(tables_data)} Dining Tables (T1-T10)"))

        # 4. Tax Configuration (CGST 2.5% + SGST 2.5%)
        TaxConfiguration.objects.get_or_create(
            name="CGST",
            defaults={'rate_percentage': Decimal('2.50'), 'is_inclusive': False, 'is_active': True}
        )
        TaxConfiguration.objects.get_or_create(
            name="SGST",
            defaults={'rate_percentage': Decimal('2.50'), 'is_inclusive': False, 'is_active': True}
        )
        self.stdout.write(self.style.SUCCESS("✓ Seeded Tax Configurations (CGST 2.5%, SGST 2.5%)"))

        # 5. Discounts
        Discount.objects.get_or_create(
            name="Staff Discount 10%",
            defaults={'discount_type': 'percentage', 'value': Decimal('10.00'), 'min_order_amount': Decimal('0.00'), 'is_active': True}
        )
        Discount.objects.get_or_create(
            name="Welcome Offer ₹30",
            defaults={'discount_type': 'fixed', 'value': Decimal('30.00'), 'min_order_amount': Decimal('200.00'), 'is_active': True}
        )
        self.stdout.write(self.style.SUCCESS("✓ Seeded Discounts"))

        # 6. Printers Configuration (Simulated mode default, configurable to USB/Ethernet)
        PrinterConfiguration.objects.get_or_create(
            printer_type="kitchen",
            defaults={
                'name': 'TVS Kitchen Thermal Printer',
                'connection_type': 'simulated',
                'device_identifier': 'virtual_kitchen_printer',
                'port': 9100,
                'paper_width_mm': 80,
                'characters_per_line': 42,
                'auto_cut': True,
                'open_cash_drawer': False,
                'is_active': True,
            }
        )
        PrinterConfiguration.objects.get_or_create(
            printer_type="billing",
            defaults={
                'name': 'TVS Counter Billing Printer',
                'connection_type': 'simulated',
                'device_identifier': 'virtual_billing_printer',
                'port': 9100,
                'paper_width_mm': 80,
                'characters_per_line': 42,
                'auto_cut': True,
                'open_cash_drawer': True,
                'is_active': True,
            }
        )
        self.stdout.write(self.style.SUCCESS("✓ Configured Kitchen & Billing Thermal Printers"))

        # 7. Categories & Menu Products
        catalog = [
            ("Shawarma", 1, [
                ("Signature Chicken Shawarma", Decimal("140.00"), "Slow-roasted shredded chicken wrapped in warm pita with homemade garlic toum and pickles."),
                ("Special Rumali Shawarma", Decimal("170.00"), "Extra meat loaded shawarma wrapped in delicate thin rumali roti."),
                ("Plate Shawarma Special", Decimal("220.00"), "Generous portion of carved chicken served with 2 kubbus, fries, hummus and pickled veggies."),
                ("Falafel Veg Shawarma", Decimal("120.00"), "Crispy spiced chickpea fritters with tahini sauce and fresh crisp greens.")
            ]),
            ("Charcoal & Grills", 2, [
                ("Al Faham Chicken (Half)", Decimal("240.00"), "Arabian charcoal-grilled chicken marinated with aromatic spices and herbs."),
                ("Peri Peri Al Faham (Half)", Decimal("260.00"), "Spicy bird-eye chili marinated flame-grilled chicken with zesty tang."),
                ("Chicken Tikka Plate", Decimal("210.00"), "Juicy tender tandoori chicken chunks with mint chutney.")
            ]),
            ("Appetizers & Sides", 3, [
                ("Crispy Salted Fries", Decimal("90.00"), "Golden potato fries tossed in sea salt, served with garlic dip."),
                ("Peri Peri Fries", Decimal("110.00"), "Crispy fries dusted with house special peri-peri spice blend."),
                ("Classic Falafel (6 pcs)", Decimal("95.00"), "Handmade crispy chickpea patties with creamy tahini.")
            ]),
            ("Beverages & Shakes", 4, [
                ("Rayara Special Sulaimani", Decimal("30.00"), "Black tea infused with cardamom, mint and a squeeze of fresh lemon."),
                ("Karak Chai", Decimal("35.00"), "Rich, slow-brewed spiced milk tea with saffron and cardamom."),
                ("Avocado Cream Shake", Decimal("130.00"), "Velvety fresh avocado blended with rich milk and honey."),
                ("Fresh Mint Limeade", Decimal("60.00"), "Chilled freshly squeezed lime with crushed garden mint.")
            ]),
            ("Desserts", 5, [
                ("Arabic Dates Pudding", Decimal("150.00"), "Warm date cake drenched in rich butterscotch sauce."),
                ("Sizzling Brownie with Ice Cream", Decimal("180.00"), "Decadent dark chocolate brownie on a hot skillet with vanilla scoop.")
            ])
        ]

        total_prods = 0
        for cat_name, order_idx, items in catalog:
            cat, _ = Category.objects.get_or_create(
                name=cat_name,
                defaults={'display_order': order_idx, 'is_active': True}
            )
            for item_name, price, desc in items:
                Product.objects.get_or_create(
                    name=item_name,
                    category=cat,
                    defaults={'price': price, 'description': desc, 'is_available': True, 'is_active': True}
                )
                total_prods += 1

        self.stdout.write(self.style.SUCCESS(f"✓ Seeded {len(catalog)} Categories and {total_prods} Menu Products"))
        self.stdout.write(self.style.SUCCESS("🎉 Rayara Cafe POS initial seed completed successfully!"))

