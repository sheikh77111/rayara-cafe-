from decimal import Decimal
from django.utils import timezone
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from pos.models import (
    BusinessSettings, DiningTable, Category, Product,
    TaxConfiguration, Discount, Order, OrderItem,
    PrinterConfiguration, PrintJob, Payment, Receipt, AuditLog
)


class Phase1EnvironmentTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_pos_app_installed(self):
        from django.apps import apps
        self.assertTrue(apps.is_installed('pos'))

    def test_pos_status_endpoint(self):
        url = reverse('pos:status')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('phase'), 1)
        self.assertEqual(data.get('status'), 'online')


class Phase2DatabaseArchitectureTests(TestCase):
    """
    Exhaustive tests for Phase 2 Database Architecture & Models.
    """
    def setUp(self):
        self.user = User.objects.create_user(username='staff_test', password='password123')
        self.category = Category.objects.create(name='Shawarma', display_order=1)
        self.product = Product.objects.create(
            category=self.category,
            name='Signature Shawarma',
            price=Decimal('150.00'),
            is_available=True
        )
        self.table = DiningTable.objects.create(number='T1', capacity=4, status='available')

        # Tax configurations (CGST 2.5% + SGST 2.5% = 5% total)
        TaxConfiguration.objects.create(name='CGST', rate_percentage=Decimal('2.50'), is_active=True)
        TaxConfiguration.objects.create(name='SGST', rate_percentage=Decimal('2.50'), is_active=True)

    def test_category_and_product_creation(self):
        """Verify Category and Product models behave correctly."""
        self.assertEqual(self.category.name, 'Shawarma')
        self.assertEqual(self.product.category, self.category)
        self.assertEqual(self.product.price, Decimal('150.00'))
        self.assertTrue(self.product.is_available)
        self.assertTrue(self.product.is_active)

    def test_table_availability_and_active_order(self):
        """Verify DiningTable active order resolution."""
        self.assertEqual(self.table.status, 'available')
        self.assertIsNone(self.table.get_active_order())

        # Create active order
        order = Order.objects.create(
            order_number=Order.generate_next_order_number('dine_in'),
            order_type='dine_in',
            table=self.table,
            created_by=self.user,
            status='new'
        )
        self.assertEqual(self.table.get_active_order(), order)

    def test_order_creation_and_price_snapshot_preservation(self):
        """
        Verify that OrderItem preserves the historical price snapshot
        even when the catalog product price changes.
        """
        order = Order.objects.create(
            order_number='D-TEST-001',
            order_type='dine_in',
            table=self.table,
            created_by=self.user
        )
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            unit_price=self.product.price,
            quantity=2
        )
        self.assertEqual(item.line_total, Decimal('300.00'))

        # Change catalog price
        self.product.price = Decimal('200.00')
        self.product.save()

        # Refresh order item from database
        item.refresh_from_db()
        self.assertEqual(item.unit_price, Decimal('150.00'), "OrderItem historical unit_price must not change when Product changes")
        self.assertEqual(item.line_total, Decimal('300.00'))

    def test_order_total_and_tax_recalculation(self):
        """
        Verify subtotal, tax calculation (5%), and grand total computation.
        """
        order = Order.objects.create(
            order_number='D-TEST-002',
            order_type='dine_in',
            table=self.table,
            created_by=self.user
        )
        # 2x Shawarma @ 150 = 300
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            unit_price=self.product.price,
            quantity=2
        )

        grand_total = order.recalculate_totals()
        # Subtotal = 300.00, Tax = 5% of 300 = 15.00, Grand total = 315.00
        self.assertEqual(order.subtotal, Decimal('300.00'))
        self.assertEqual(order.tax_amount, Decimal('15.00'))
        self.assertEqual(order.grand_total, Decimal('315.00'))
        self.assertEqual(grand_total, Decimal('315.00'))

    def test_item_cancellation_adjusts_totals(self):
        """
        Verify that cancelling an item excludes it from the order totals.
        """
        order = Order.objects.create(
            order_number='D-TEST-003',
            order_type='dine_in',
            table=self.table,
            created_by=self.user
        )
        item1 = OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal('100.00'),
            quantity=1
        )
        item2 = OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal('50.00'),
            quantity=1
        )
        order.recalculate_totals()
        self.assertEqual(order.subtotal, Decimal('150.00'))

        # Cancel item 2
        item2.is_cancelled = True
        item2.cancellation_reason = "Customer changed mind"
        item2.save()

        order.recalculate_totals()
        # Now only item1 (100.00) + 5% tax (5.00) = 105.00
        self.assertEqual(order.subtotal, Decimal('100.00'))
        self.assertEqual(order.tax_amount, Decimal('5.00'))
        self.assertEqual(order.grand_total, Decimal('105.00'))

    def test_print_job_idempotency(self):
        """
        Verify that PrintJob enforces idempotency keys to prevent duplicate printing.
        """
        order = Order.objects.create(
            order_number='D-TEST-004',
            order_type='takeaway',
            created_by=self.user
        )
        job1 = PrintJob.objects.create(
            idempotency_key='KITCHEN-D-TEST-004-BATCH-1',
            printer_type='kitchen',
            job_type='new_order',
            order=order,
            content='TICKET CONTENT'
        )
        self.assertIsNotNone(job1.id)

        # Attempting to create duplicate job with same idempotency key must raise IntegrityError
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            PrintJob.objects.create(
                idempotency_key='KITCHEN-D-TEST-004-BATCH-1',
                printer_type='kitchen',
                job_type='new_order',
                order=order,
                content='TICKET CONTENT'
            )

    def test_payment_and_receipt_creation(self):
        """
        Verify payment recording and immutable customer receipt issuance.
        """
        order = Order.objects.create(
            order_number='D-TEST-005',
            order_type='takeaway',
            created_by=self.user,
            subtotal=Decimal('200.00'),
            tax_amount=Decimal('10.00'),
            grand_total=Decimal('210.00'),
            is_paid=True
        )
        payment = Payment.objects.create(
            order=order,
            amount=Decimal('210.00'),
            payment_method='upi',
            reference_number='UPI123456789',
            received_by=self.user
        )
        receipt = Receipt.objects.create(
            receipt_number=Receipt.generate_next_receipt_number(),
            order=order,
            subtotal=order.subtotal,
            tax_amount=order.tax_amount,
            grand_total=order.grand_total,
            payment_method='upi',
            issued_by=self.user
        )
        self.assertEqual(receipt.grand_total, Decimal('210.00'))
        self.assertFalse(receipt.is_reprint)
        self.assertEqual(receipt.reprint_count, 0)
        self.assertTrue(receipt.receipt_number.startswith('RCP-'))


class Phase3AuthenticationTests(TestCase):
    """
    Exhaustive tests for Phase 3: Authentication and Role-Based Permissions (RBAC).
    """
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_superuser(username='owner_admin', password='ownerpassword')
        self.staff = User.objects.create_user(username='waiter_staff', password='staffpassword', is_staff=True)

    def test_unauthenticated_user_redirected_to_login(self):
        """Unauthenticated requests to protected POS routes must redirect to staff login."""
        response = self.client.get(reverse('pos:tablet'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/pos/staff/login/', response.url)

    def test_staff_login_via_dedicated_portal(self):
        """Staff login on dedicated /pos/staff/login/ portal redirects to tablet interface."""
        response = self.client.post(reverse('pos:staff_login'), {
            'username': 'waiter_staff',
            'password': 'staffpassword'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertEqual(response.context['user'].username, 'waiter_staff')

    def test_owner_login_via_dedicated_portal(self):
        """Owner login on dedicated /pos/admin/login/ portal redirects to owner dashboard."""
        response = self.client.post(reverse('pos:owner_login'), {
            'username': 'owner_admin',
            'password': 'ownerpassword'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertTrue(response.context['user'].is_superuser)

    def test_staff_cannot_login_on_owner_portal(self):
        """Staff attempting to sign in on /pos/admin/login/ must be strictly rejected."""
        response = self.client.post(reverse('pos:owner_login'), {
            'username': 'waiter_staff',
            'password': 'staffpassword'
        })
        self.assertEqual(response.status_code, 200)
        # Session must not be authenticated as owner
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_customer_user_cannot_login_on_staff_portal(self):
        """Unprivileged customer account cannot login on staff portal."""
        User.objects.create_user(username='customer_diner', password='dinerpassword', is_staff=False)
        response = self.client.post(reverse('pos:staff_login'), {
            'username': 'customer_diner',
            'password': 'dinerpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_staff_cannot_access_owner_dashboard(self):
        """Staff user must be denied access from owner admin dashboard."""
        self.client.login(username='waiter_staff', password='staffpassword')
        response = self.client.get(reverse('pos:owner_dashboard'))
        # Must redirect back to tablet or return 403
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/pos/tablet/')

    def test_owner_can_access_owner_dashboard(self):
        """Owner/superuser can access owner dashboard."""
        self.client.login(username='owner_admin', password='ownerpassword')
        response = self.client.get(reverse('pos:owner_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_json_api_login_success_and_role_detection(self):
        """JSON API login returns correct roles and redirect paths."""
        # Staff API login
        resp_staff = self.client.post(
            reverse('pos:api_login'),
            data={'username': 'waiter_staff', 'password': 'staffpassword'},
            content_type='application/json'
        )
        self.assertEqual(resp_staff.status_code, 200)
        data_staff = resp_staff.json()
        self.assertTrue(data_staff.get('success'))
        self.assertFalse(data_staff['user']['is_owner'])
        self.assertTrue(data_staff['user']['is_staff'])
        self.assertEqual(data_staff['redirect'], '/pos/tablet/')

        # Owner API login
        resp_owner = self.client.post(
            reverse('pos:api_login'),
            data={'username': 'owner_admin', 'password': 'ownerpassword'},
            content_type='application/json'
        )
        self.assertEqual(resp_owner.status_code, 200)
        data_owner = resp_owner.json()
        self.assertTrue(data_owner['user']['is_owner'])
        self.assertEqual(data_owner['redirect'], '/pos/admin/')

    def test_invalid_login_rejected(self):
        """Invalid credentials must return 401 on API and error message on form."""
        resp = self.client.post(
            reverse('pos:api_login'),
            data={'username': 'waiter_staff', 'password': 'wrongpassword'},
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 401)
        self.assertIn('Invalid username or password', resp.json().get('error'))

    def test_logout_clears_session(self):
        """Logout clears authentication session and redirects."""
        self.client.login(username='waiter_staff', password='staffpassword')
        resp = self.client.get(reverse('pos:logout'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/pos/staff/login/', resp.url)
        # Follow-up request to tablet should be redirected to staff login
        resp_tablet = self.client.get(reverse('pos:tablet'))
        self.assertEqual(resp_tablet.status_code, 302)
        self.assertIn('/pos/staff/login/', resp_tablet.url)
        self.assertEqual(resp_tablet.status_code, 302)



class Phase4And5POSWorkflowTests(TestCase):
    """
    Exhaustive integration tests for Connected POS Ordering, Kitchen Printing,
    Coupon Validation, Digital Bills and Management APIs.
    """
    def setUp(self):
        from core.models import Customer, Coupon, Reward, Game
        from core.views import digest
        from datetime import timedelta

        self.client = Client()

        # Staff and Owner Users
        self.staff_user = User.objects.create_user(username='staff_test', password='staffpassword', is_staff=True)
        self.owner_user = User.objects.create_superuser(username='owner_test', password='ownerpassword')

        # Business Settings & Taxes
        BusinessSettings.get_settings()
        TaxConfiguration.objects.get_or_create(name='CGST', defaults={'rate_percentage': Decimal('2.50'), 'is_active': True})
        TaxConfiguration.objects.get_or_create(name='SGST', defaults={'rate_percentage': Decimal('2.50'), 'is_active': True})

        # Printer Configurations (Simulated)
        PrinterConfiguration.objects.get_or_create(
            printer_type='kitchen',
            defaults={'name': 'TVS Kitchen Printer', 'connection_type': 'simulated', 'device_identifier': 'virtual'}
        )
        PrinterConfiguration.objects.get_or_create(
            printer_type='billing',
            defaults={'name': 'TVS Billing Printer', 'connection_type': 'simulated', 'device_identifier': 'virtual'}
        )

        # Tables
        self.table_t1 = DiningTable.objects.create(number='T1', capacity=4, status='available')
        self.table_t2 = DiningTable.objects.create(number='T2', capacity=2, status='available')

        # Menu
        self.cat_shawarma = Category.objects.create(name='Shawarma', display_order=1)
        self.cat_drinks = Category.objects.create(name='Beverages', display_order=2)

        self.item_shawarma = Product.objects.create(
            category=self.cat_shawarma,
            name='Chicken Shawarma',
            price=Decimal('120.00'),
            is_available=True
        )
        self.item_lime = Product.objects.create(
            category=self.cat_drinks,
            name='Fresh Lime',
            price=Decimal('50.00'),
            is_available=True
        )

        # Customer & Coupons in core
        self.customer = Customer.objects.create(
            email='guest@rayaracafe.com',
            phone_number='9876543210'
        )

        # 20% active coupon e.g. RAYARA20X8
        self.plain_coupon_code = 'RAYARA20X8'
        self.active_coupon = Coupon.objects.create(
            customer=self.customer,
            email=self.customer.email,
            phone_number=self.customer.phone_number,
            code_plain=self.plain_coupon_code,
            code_hash=digest(self.plain_coupon_code),
            code_hint='20X8',
            percentage=20,
            minimum_spend=Decimal('199.00'),
            max_discount=Decimal('100.00'),
            valid_from=timezone.now() - timedelta(days=1),
            expires_at=timezone.now() + timedelta(days=7),
            status='active'
        )

        # Expired coupon
        self.expired_coupon = Coupon.objects.create(
            customer=self.customer,
            email=self.customer.email,
            code_plain='EXPIRED99',
            code_hash=digest('EXPIRED99'),
            code_hint='ED99',
            percentage=10,
            minimum_spend=Decimal('100.00'),
            max_discount=Decimal('50.00'),
            valid_from=timezone.now() - timedelta(days=10),
            expires_at=timezone.now() - timedelta(days=1),
            status='expired'
        )

    def test_api_tables_listing(self):
        """Staff can list dining tables with active orders."""
        self.client.login(username='staff_test', password='staffpassword')
        resp = self.client.get(reverse('pos:api_tables'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['number'], 'T1')
        self.assertEqual(data[0]['status'], 'available')

    def test_api_menu_listing(self):
        """Menu endpoint returns categories and products."""
        resp = self.client.get(reverse('pos:api_menu'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(len(data), 2)
        # Check shawarma product
        cat1 = next(c for c in data if c['name'] == 'Shawarma')
        self.assertEqual(cat1['products'][0]['name'], 'Chicken Shawarma')
        self.assertEqual(cat1['products'][0]['price'], '120.00')

    def test_create_dine_in_order_with_kitchen_print(self):
        """
        Staff creates Dine-in order for Table T1:
        - Validates table availability
        - Generates order number (e.g. D-YYMMDD-XXX)
        - Computes totals: 2 Shawarma (240) + 2 Fresh Lime (100) = Subtotal 340 + 5% tax = 357.00
        - Marks Table T1 as occupied
        - Queues persistent kitchen PrintJob (KOT)
        """
        self.client.login(username='staff_test', password='staffpassword')
        payload = {
            'order_type': 'dine_in',
            'table_number': 'T1',
            'items': [
                {'product_id': self.item_shawarma.id, 'quantity': 2, 'special_instructions': 'Extra spicy'},
                {'product_id': self.item_lime.id, 'quantity': 2, 'special_instructions': 'Less sugar'}
            ]
        }
        resp = self.client.post(
            reverse('pos:api_order_create'),
            data=payload,
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertTrue(data['success'])
        order_id = data['order_id']

        order = Order.objects.get(id=order_id)
        self.assertEqual(order.subtotal, Decimal('340.00'))
        self.assertEqual(order.grand_total, Decimal('357.00'))  # 340 + 5% GST (17.00)
        self.assertEqual(order.current_batch, 1)

        # Verify Table status changed to occupied
        self.table_t1.refresh_from_db()
        self.assertEqual(self.table_t1.status, 'occupied')

        # Verify KOT print job was created and dispatched
        kot_job = PrintJob.objects.filter(order=order, printer_type='kitchen').first()
        self.assertIsNotNone(kot_job)
        self.assertEqual(kot_job.job_type, 'new_order')
        self.assertIn('CHICKEN SHAWARMA', kot_job.content.upper())
        self.assertIn('TABLE T1', kot_job.content.upper())
        self.assertEqual(kot_job.status, 'printed')

    def test_prevent_duplicate_dine_in_order_for_same_table(self):
        """Attempting to create another order on an already occupied table returns 409 conflict."""
        self.client.login(username='staff_test', password='staffpassword')
        # Mark table T1 as occupied with active order
        self.table_t1.status = 'occupied'
        self.table_t1.save()
        Order.objects.create(
            order_number='D-EXISTING-01',
            order_type='dine_in',
            table=self.table_t1,
            created_by=self.staff_user,
            status='new'
        )

        payload = {
            'order_type': 'dine_in',
            'table_number': 'T1',
            'items': [{'product_id': self.item_shawarma.id, 'quantity': 1}]
        }
        resp = self.client.post(
            reverse('pos:api_order_create'),
            data=payload,
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 409)
        self.assertTrue(resp.json().get('table_occupied'))

    def test_add_items_to_active_order(self):
        """
        Waiter adds additional items (Batch #2) to active order:
        - Order batch increments to 2
        - Line items tagged with batch_number=2
        - Add-on KOT print job queued
        """
        self.client.login(username='staff_test', password='staffpassword')
        order = Order.objects.create(
            order_number='D-TEST-ADD',
            order_type='dine_in',
            table=self.table_t1,
            created_by=self.staff_user,
            current_batch=1
        )
        OrderItem.objects.create(
            order=order, product=self.item_shawarma, product_name=self.item_shawarma.name,
            unit_price=self.item_shawarma.price, quantity=1, batch_number=1
        )
        order.recalculate_totals()

        payload = {
            'order_id': order.id,
            'items': [
                {'product_id': self.item_lime.id, 'quantity': 2, 'special_instructions': 'Cold'}
            ]
        }
        resp = self.client.post(
            reverse('pos:api_order_add_items'),
            data=payload,
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.current_batch, 2)
        self.assertEqual(order.items.count(), 2)

        # Check add-on KOT
        add_job = PrintJob.objects.filter(order=order, job_type='additional_order').first()
        self.assertIsNotNone(add_job)
        self.assertIn('BATCH #2', add_job.content)

    def test_cancel_item_and_recalculate_totals(self):
        """Cancelling an unserved item recalculates financials and alerts kitchen."""
        self.client.login(username='staff_test', password='staffpassword')
        order = Order.objects.create(
            order_number='D-CANCEL-TEST',
            order_type='dine_in',
            table=self.table_t1,
            created_by=self.staff_user
        )
        item1 = OrderItem.objects.create(
            order=order, product=self.item_shawarma, product_name=self.item_shawarma.name,
            unit_price=self.item_shawarma.price, quantity=2, batch_number=1
        )
        item2 = OrderItem.objects.create(
            order=order, product=self.item_lime, product_name=self.item_lime.name,
            unit_price=self.item_lime.price, quantity=1, batch_number=1
        )
        order.recalculate_totals()
        self.assertEqual(order.subtotal, Decimal('290.00'))  # (120*2) + 50

        # Cancel item 2 (Fresh Lime)
        resp = self.client.post(
            reverse('pos:api_order_cancel_item'),
            data={'item_id': item2.id, 'reason': 'Customer changed mind'},
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)

        item2.refresh_from_db()
        self.assertTrue(item2.is_cancelled)
        self.assertEqual(item2.cancellation_reason, 'Customer changed mind')

        order.refresh_from_db()
        self.assertEqual(order.subtotal, Decimal('240.00'))  # Lime subtracted

        # Verify cancel print job
        cancel_job = PrintJob.objects.filter(order=order, job_type='cancelled_item').first()
        self.assertIsNotNone(cancel_job)
        self.assertIn('CANCELLED ITEM ALERT', cancel_job.content)

    def test_validate_customer_coupon(self):
        """
        Billing Counter validates genuine customer coupon:
        Subtotal = ₹340.00
        20% Coupon = -₹68.00 discount
        Taxable = ₹272.00
        5% Tax (CGST 2.5% + SGST 2.5%) = ₹13.60
        Payable = ₹285.60
        """
        self.client.login(username='staff_test', password='staffpassword')
        order = Order.objects.create(
            order_number='D-VAL-COUPON',
            order_type='dine_in',
            table=self.table_t1,
            created_by=self.staff_user,
            subtotal=Decimal('340.00')
        )

        resp = self.client.post(
            reverse('pos:api_validate_coupon'),
            data={'order_id': order.id, 'coupon_code': self.plain_coupon_code},
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['valid'])
        self.assertEqual(data['percentage'], 20)
        self.assertEqual(data['discount_amount'], '68.00')
        self.assertEqual(data['payable_total'], '285.60')

    def test_reject_expired_coupon(self):
        """Billing counter rejects expired coupons."""
        self.client.login(username='staff_test', password='staffpassword')
        resp = self.client.post(
            reverse('pos:api_validate_coupon'),
            data={'subtotal': '300.00', 'coupon_code': 'EXPIRED99'},
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json().get('valid'))
        self.assertIn('expired', resp.json().get('error').lower())

    def test_settle_payment_and_free_table(self):
        """
        Settling payment:
        - Marks order as paid & completed
        - Marks coupon as redeemed (preventing duplicate redemption)
        - Issues immutable Receipt
        - Frees table back to available
        - Dispatches counter thermal receipt PrintJob
        """
        self.client.login(username='staff_test', password='staffpassword')
        self.table_t1.status = 'occupied'
        self.table_t1.save()

        order = Order.objects.create(
            order_number='D-SETTLE-01',
            order_type='dine_in',
            table=self.table_t1,
            created_by=self.staff_user
        )
        OrderItem.objects.create(
            order=order, product=self.item_shawarma, product_name=self.item_shawarma.name,
            unit_price=self.item_shawarma.price, quantity=2, batch_number=1
        )
        OrderItem.objects.create(
            order=order, product=self.item_lime, product_name=self.item_lime.name,
            unit_price=self.item_lime.price, quantity=2, batch_number=1
        )
        order.recalculate_totals()

        payload = {
            'order_id': order.id,
            'payment_method': 'upi',
            'reference_number': 'UPI987654321',
            'coupon_code': self.plain_coupon_code,
            'customer_email': self.customer.email,
            'customer_phone': self.customer.phone_number
        }
        resp = self.client.post(
            reverse('pos:api_settle_payment'),
            data=payload,
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

        order.refresh_from_db()
        self.assertTrue(order.is_paid)
        self.assertEqual(order.status, 'completed')
        self.assertEqual(order.discount_amount, Decimal('68.00'))

        # Coupon must be redeemed
        self.active_coupon.refresh_from_db()
        self.assertEqual(self.active_coupon.status, 'redeemed')

        # Table must be freed
        self.table_t1.refresh_from_db()
        self.assertEqual(self.table_t1.status, 'available')

        # Receipt must exist
        self.assertTrue(Receipt.objects.filter(order=order).exists())
        rcp = order.receipt
        self.assertEqual(rcp.payment_method, 'upi')
        self.assertEqual(rcp.discount_amount, Decimal('68.00'))

        # PrintJob for billing counter created
        bill_job = PrintJob.objects.filter(order=order, printer_type='billing').first()
        self.assertIsNotNone(bill_job)
        self.assertIn('TAX INVOICE', bill_job.content)
        self.assertIn('Payment Mode: UPI', bill_job.content)

    def test_customer_digital_bills_endpoint(self):
        """Customer can view their settled digital receipts."""
        # Create a paid receipt for the test customer
        order = Order.objects.create(
            order_number='D-DIGITAL-01',
            order_type='dine_in',
            table=self.table_t1,
            created_by=self.staff_user,
            customer=self.customer,
            is_paid=True,
            status='completed'
        )
        OrderItem.objects.create(
            order=order, product=self.item_shawarma, product_name=self.item_shawarma.name,
            unit_price=self.item_shawarma.price, quantity=2
        )
        order.recalculate_totals()
        receipt = Receipt.objects.create(
            receipt_number=Receipt.generate_next_receipt_number(),
            order=order,
            subtotal=order.subtotal,
            discount_amount=Decimal('0.00'),
            tax_amount=order.tax_amount,
            grand_total=order.grand_total,
            payment_method='cash',
            issued_by=self.staff_user
        )

        resp = self.client.get(f"{reverse('pos:api_customer_bills')}?email={self.customer.email}")
        self.assertEqual(resp.status_code, 200)
        bills = resp.json()
        self.assertGreaterEqual(len(bills), 1)
        self.assertEqual(bills[0]['receipt_number'], receipt.receipt_number)
        self.assertEqual(bills[0]['items'][0]['name'], 'Chicken Shawarma')

    def test_admin_metrics_and_product_toggle(self):
        """Owner can view live metrics and toggle product stock status."""
        self.client.login(username='owner_test', password='ownerpassword')

        # Check metrics
        resp_metrics = self.client.get(reverse('pos:api_admin_metrics'))
        self.assertEqual(resp_metrics.status_code, 200)
        self.assertIn('today_sales', resp_metrics.json())

        # Toggle product stock
        self.assertTrue(self.item_shawarma.is_available)
        resp_toggle = self.client.post(
            reverse('pos:api_admin_toggle_product'),
            data={'product_id': self.item_shawarma.id},
            content_type='application/json'
        )
        self.assertEqual(resp_toggle.status_code, 200)
        self.assertFalse(resp_toggle.json()['is_available'])
        self.item_shawarma.refresh_from_db()
        self.assertFalse(self.item_shawarma.is_available)

    def test_thermal_print_worker(self):
        """Print worker processes pending print jobs."""
        from pos.printer import process_pending_print_jobs
        order = Order.objects.create(
            order_number='D-WORKER-01',
            order_type='dine_in',
            table=self.table_t1,
            created_by=self.staff_user
        )
        job = PrintJob.objects.create(
            idempotency_key='TEST-WORKER-KEY',
            printer_type='kitchen',
            job_type='new_order',
            order=order,
            content='Test Worker KOT Content',
            status='pending'
        )
        processed = process_pending_print_jobs()
        self.assertGreaterEqual(processed, 1)
        job.refresh_from_db()
        self.assertEqual(job.status, 'printed')
