from decimal import Decimal
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

