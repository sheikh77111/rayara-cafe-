import uuid
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Count, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from core.views import digest
from core.models import Customer, Coupon, Redemption
from .models import (
    BusinessSettings, DiningTable, Category, Product,
    TaxConfiguration, Discount, Order, OrderItem,
    PrinterConfiguration, PrintJob, Payment, Receipt, AuditLog
)
from .permissions import is_owner, is_staff_member, IsOwnerUser, IsStaffOrOwnerUser
from .printer import (
    format_kitchen_ticket, format_receipt_ticket,
    dispatch_print_job
)


# ==============================================================================
# STAFF TABLET APIs
# ==============================================================================

@api_view(['GET'])
@permission_classes([IsStaffOrOwnerUser])
def api_tables(request):
    """
    Returns list of all restaurant tables and their current live status.
    """
    tables = DiningTable.objects.filter(is_active=True).order_by('number')
    result = []
    for t in tables:
        active_order = t.get_active_order()
        order_data = None
        if active_order:
            order_data = {
                'id': active_order.id,
                'order_number': active_order.order_number,
                'status': active_order.status,
                'subtotal': str(active_order.subtotal),
                'grand_total': str(active_order.grand_total),
                'items_count': active_order.items.filter(is_cancelled=False).count(),
                'current_batch': active_order.current_batch,
                'created_at': active_order.created_at.isoformat(),
            }
        result.append({
            'id': t.id,
            'number': t.number,
            'capacity': t.capacity,
            'status': t.status,
            'active_order': order_data
        })
    return Response(result)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_menu(request):
    """
    Returns menu categories and food products. Available to tablet, billing, and customer portals.
    """
    cats = Category.objects.filter(is_active=True).prefetch_related('products').order_by('display_order', 'name')
    result = []
    for c in cats:
        products = c.products.filter(is_active=True).order_by('name')
        prods_data = []
        for p in products:
            img_url = p.image.url if p.image else ''
            prods_data.append({
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'price': str(p.price),
                'image_url': img_url,
                'is_available': p.is_available,
                'category_id': c.id,
                'category_name': c.name
            })
        result.append({
            'id': c.id,
            'name': c.name,
            'display_order': c.display_order,
            'products': prods_data
        })
    return Response(result)


@api_view(['POST'])
@permission_classes([IsStaffOrOwnerUser])
def api_order_create(request):
    """
    Creates a new Dine-in or Takeaway order and sends KOT to kitchen printer.
    """
    data = request.data
    order_type = data.get('order_type', 'dine_in')
    table_number = data.get('table_number', '').strip()
    customer_name = data.get('customer_name', '').strip()
    customer_phone = data.get('customer_phone', '').strip()
    takeaway_notes = data.get('takeaway_notes', '').strip()
    items_data = data.get('items', [])

    if not items_data:
        return Response({'error': 'Order must contain at least one item.'}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        table = None
        if order_type == 'dine_in':
            if not table_number:
                return Response({'error': 'Table selection is required for Dine-in orders.'}, status=status.HTTP_400_BAD_REQUEST)
            table = DiningTable.objects.select_for_update().filter(number=table_number, is_active=True).first()
            if not table:
                return Response({'error': f'Table {table_number} does not exist.'}, status=status.HTTP_404_NOT_FOUND)
            if table.status == 'occupied':
                # Return error prompting to add items to existing order
                active_order = table.get_active_order()
                return Response({
                    'error': f'Table {table_number} already has an active order ({active_order.order_number if active_order else ""}). Use "Add Items" instead.',
                    'table_occupied': True,
                    'existing_order_id': active_order.id if active_order else None
                }, status=status.HTTP_409_CONFLICT)

        order = None
        for attempt in range(5):
            order_num = Order.generate_next_order_number(order_type=order_type)
            try:
                with transaction.atomic():
                    order = Order.objects.create(
                        order_number=order_num,
                        order_type=order_type,
                        table=table,
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                        takeaway_notes=takeaway_notes,
                        status='new',
                        created_by=request.user,
                        current_batch=1
                    )
                break
            except Exception:
                if attempt == 4:
                    raise

        created_items = []
        for it in items_data:
            prod_id = it.get('product_id')
            qty = int(it.get('quantity', 1))
            note = it.get('special_instructions', '').strip()
            if qty <= 0:
                continue
            product = Product.objects.filter(id=prod_id, is_active=True).first()
            if not product:
                continue

            order_item = OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                unit_price=product.price,
                quantity=qty,
                special_instructions=note,
                batch_number=1,
                status='ordered'
            )
            created_items.append(order_item)

        if not created_items:
            raise ValueError("No valid products were added to the order.")

        # Recalculate totals
        order.recalculate_totals()

        # Update table status
        if table:
            table.status = 'occupied'
            table.save(update_fields=['status'])

        # Queue persistent kitchen PrintJob
        preview_text, _ = format_kitchen_ticket(order, created_items, job_type='new_order', batch_number=1)
        job = PrintJob.objects.create(
            idempotency_key=f"KOT-{order.order_number}-B1",
            printer_type='kitchen',
            job_type='new_order',
            order=order,
            content=preview_text
        )

        # Dispatch printing immediately
        dispatch_print_job(job)

        AuditLog.objects.create(
            user=request.user,
            action='order_created',
            entity_type='order',
            entity_id=str(order.id),
            details=f"Order {order.order_number} created with {len(created_items)} items for {table.number if table else 'Takeaway'}",
            ip_address=request.META.get('REMOTE_ADDR', '')
        )

        return Response({
            'success': True,
            'message': f'Order {order.order_number} sent to kitchen!',
            'order_id': order.id,
            'order_number': order.order_number,
            'subtotal': str(order.subtotal),
            'grand_total': str(order.grand_total),
            'batch': 1,
            'print_job_id': job.id,
            'print_status': job.status
        }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsStaffOrOwnerUser])
def api_order_add_items(request):
    """
    Adds additional food items to an existing active order (Batch 2+).
    Prints add-on KOT to the kitchen printer.
    """
    data = request.data
    order_id = data.get('order_id')
    items_data = data.get('items', [])

    if not order_id or not items_data:
        return Response({'error': 'Order ID and items list are required.'}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        order = Order.objects.select_for_update().filter(id=order_id).first()
        if not order:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)
        if order.status in ('completed', 'cancelled') or order.is_paid:
            return Response({'error': 'Cannot add items to completed or paid orders.'}, status=status.HTTP_400_BAD_REQUEST)

        order.current_batch += 1
        new_batch = order.current_batch
        order.save(update_fields=['current_batch'])

        new_items = []
        for it in items_data:
            prod_id = it.get('product_id')
            qty = int(it.get('quantity', 1))
            note = it.get('special_instructions', '').strip()
            if qty <= 0:
                continue
            product = Product.objects.filter(id=prod_id, is_active=True).first()
            if not product:
                continue

            order_item = OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                unit_price=product.price,
                quantity=qty,
                special_instructions=note,
                batch_number=new_batch,
                status='ordered'
            )
            new_items.append(order_item)

        if not new_items:
            return Response({'error': 'No valid items were added.'}, status=status.HTTP_400_BAD_REQUEST)

        order.recalculate_totals()

        # Format and queue add-on kitchen ticket
        preview_text, _ = format_kitchen_ticket(order, new_items, job_type='additional_order', batch_number=new_batch)
        job = PrintJob.objects.create(
            idempotency_key=f"KOT-{order.order_number}-B{new_batch}",
            printer_type='kitchen',
            job_type='additional_order',
            order=order,
            content=preview_text
        )
        dispatch_print_job(job)

        AuditLog.objects.create(
            user=request.user,
            action='order_items_added',
            entity_type='order',
            entity_id=str(order.id),
            details=f"Added {len(new_items)} items in Batch #{new_batch} to {order.order_number}",
            ip_address=request.META.get('REMOTE_ADDR', '')
        )

        return Response({
            'success': True,
            'message': f'Additional items sent to kitchen (Batch #{new_batch})!',
            'order_id': order.id,
            'order_number': order.order_number,
            'batch': new_batch,
            'grand_total': str(order.grand_total),
            'print_job_id': job.id
        })


@api_view(['POST'])
@permission_classes([IsStaffOrOwnerUser])
def api_order_cancel_item(request):
    """
    Cancels an unserved order item, updates order financials and prints alert to kitchen.
    """
    data = request.data
    item_id = data.get('item_id')
    reason = data.get('reason', 'Customer request').strip()

    if not item_id:
        return Response({'error': 'Item ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        item = OrderItem.objects.select_for_update().filter(id=item_id).first()
        if not item:
            return Response({'error': 'Order item not found.'}, status=status.HTTP_404_NOT_FOUND)
        if item.is_cancelled:
            return Response({'error': 'This item is already cancelled.'}, status=status.HTTP_400_BAD_REQUEST)
        if item.order.is_paid:
            return Response({'error': 'Cannot cancel items on settled orders.'}, status=status.HTTP_400_BAD_REQUEST)

        item.is_cancelled = True
        item.cancellation_reason = reason
        item.cancelled_at = timezone.now()
        item.cancelled_by = request.user
        item.status = 'cancelled'
        item.save(update_fields=['is_cancelled', 'cancellation_reason', 'cancelled_at', 'cancelled_by', 'status'])

        # Recalculate order financials
        item.order.recalculate_totals()

        # Print cancellation notice to kitchen
        preview_text, _ = format_kitchen_ticket(item.order, [item], job_type='cancelled_item', reason=reason)
        job = PrintJob.objects.create(
            idempotency_key=f"KOT-CANCEL-{item.id}-{timezone.now().timestamp()}",
            printer_type='kitchen',
            job_type='cancelled_item',
            order=item.order,
            content=preview_text
        )
        dispatch_print_job(job)

        AuditLog.objects.create(
            user=request.user,
            action='order_item_cancelled',
            entity_type='order_item',
            entity_id=str(item.id),
            details=f"Item '{item.product_name}' cancelled on {item.order.order_number}. Reason: {reason}",
            ip_address=request.META.get('REMOTE_ADDR', '')
        )

        return Response({
            'success': True,
            'message': f"Item '{item.product_name}' has been cancelled.",
            'new_grand_total': str(item.order.grand_total)
        })


@api_view(['GET'])
@permission_classes([IsStaffOrOwnerUser])
def api_active_orders(request):
    """
    Returns live active orders for staff tablet and billing counter.
    """
    orders = Order.objects.filter(is_paid=False, status__in=['new', 'preparing', 'ready']).order_by('-created_at')
    result = []
    for ord in orders:
        items = []
        for it in ord.items.all():
            items.append({
                'id': it.id,
                'name': it.product_name,
                'unit_price': str(it.unit_price),
                'quantity': it.quantity,
                'line_total': str(it.line_total),
                'batch_number': it.batch_number,
                'special_instructions': it.special_instructions,
                'is_cancelled': it.is_cancelled,
                'status': it.status
            })
        result.append({
            'id': ord.id,
            'order_number': ord.order_number,
            'order_type': ord.order_type,
            'table_number': ord.table.number if ord.table else None,
            'customer_name': ord.customer_name,
            'customer_phone': ord.customer_phone,
            'status': ord.status,
            'subtotal': str(ord.subtotal),
            'discount_amount': str(ord.discount_amount),
            'tax_amount': str(ord.tax_amount),
            'grand_total': str(ord.grand_total),
            'created_at': ord.created_at.isoformat(),
            'current_batch': ord.current_batch,
            'items': items
        })
    return Response(result)


# ==============================================================================
# BILLING COUNTER & CUSTOMER COUPON VALIDATION APIs
# ==============================================================================

@api_view(['POST'])
@permission_classes([IsStaffOrOwnerUser])
def api_validate_coupon(request):
    """
    Validates a customer coupon code, QR code text, or customer lookup.
    Calculates the exact discount server-side according to restaurant rules.
    """
    raw_code = request.data.get('coupon_code', '').strip()
    customer_phone = request.data.get('customer_phone', '').strip()
    customer_email = request.data.get('customer_email', '').strip()
    order_id = request.data.get('order_id')
    raw_amount = request.data.get('subtotal')

    # Resolve subtotal
    subtotal = Decimal('0.00')
    order = None
    if order_id:
        order = Order.objects.filter(id=order_id).first()
        if order:
            subtotal = order.subtotal
    if subtotal == Decimal('0.00') and raw_amount:
        try:
            subtotal = Decimal(str(raw_amount))
        except Exception:
            pass

    if subtotal <= Decimal('0.00'):
        return Response({'error': 'Order subtotal must be greater than zero.'}, status=status.HTTP_400_BAD_REQUEST)

    # Locate coupon
    coupon = None
    if raw_code:
        upper_code = raw_code.upper()
        # 1. Exact match on plain code
        coupon = Coupon.objects.filter(code_plain__iexact=upper_code).first()
        # 2. Hash match
        if not coupon:
            coupon = Coupon.objects.filter(code_hash=digest(upper_code)).first()
        if not coupon:
            coupon = Coupon.objects.filter(code_hash=digest(raw_code)).first()
        # 3. Hint match if unique
        if not coupon and len(raw_code) >= 4:
            possible = Coupon.objects.filter(code_hint__iexact=raw_code[-4:], status='active')
            if possible.count() == 1:
                coupon = possible.first()

    # Search by customer email/phone if code not supplied or not found
    if not coupon and customer_email:
        coupon = Coupon.objects.filter(email__iexact=customer_email.strip(), status='active').order_by('-issued_at').first()
    if not coupon and customer_phone:
        coupon = Coupon.objects.filter(phone_number=customer_phone, status='active').order_by('-issued_at').first()

    if not coupon:
        return Response({
            'valid': False,
            'error': 'Coupon not found. Please verify the code or customer details.'
        }, status=status.HTTP_404_NOT_FOUND)

    # Validation Checks
    now = timezone.now()
    if coupon.status == 'redeemed':
        return Response({
            'valid': False,
            'error': f'This coupon has already been redeemed.'
        }, status=status.HTTP_400_BAD_REQUEST)

    if coupon.status == 'expired' or now >= coupon.expires_at:
        coupon.status = 'expired'
        coupon.save(update_fields=['status'])
        return Response({
            'valid': False,
            'error': f'This coupon expired on {coupon.expires_at.strftime("%d-%b-%Y")}.'
        }, status=status.HTTP_400_BAD_REQUEST)

    if subtotal < coupon.minimum_spend:
        return Response({
            'valid': False,
            'error': f'Minimum order amount of ₹{coupon.minimum_spend} required. Current subtotal is ₹{subtotal}.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Calculate server-side discount
    percentage = Decimal(str(coupon.percentage))
    raw_discount = (subtotal * (percentage / Decimal('100.00'))).quantize(Decimal('0.01'))
    discount_amount = min(raw_discount, Decimal(str(coupon.max_discount)))

    taxable = max(Decimal('0.00'), subtotal - discount_amount)
    active_taxes = TaxConfiguration.objects.filter(is_active=True, is_inclusive=False)
    total_tax_rate = sum((t.rate_percentage for t in active_taxes), Decimal('0.00'))
    tax_amount = (taxable * (total_tax_rate / Decimal('100.00'))).quantize(Decimal('0.01'))
    payable_total = (taxable + tax_amount).quantize(Decimal('0.01'))

    display_code = coupon.code_plain if coupon.code_plain else f"RAYA-*{coupon.code_hint}"

    return Response({
        'valid': True,
        'coupon_id': coupon.id,
        'coupon_code': display_code,
        'percentage': coupon.percentage,
        'discount_amount': str(discount_amount),
        'subtotal': str(subtotal),
        'tax_amount': str(tax_amount),
        'payable_total': str(payable_total),
        'minimum_spend': str(coupon.minimum_spend),
        'max_discount': str(coupon.max_discount),
        'customer_email': coupon.email,
        'customer_phone': coupon.phone_number,
        'message': f'Success! {coupon.percentage}% coupon applied (Saved ₹{discount_amount}).'
    })


@api_view(['POST'])
@permission_classes([IsStaffOrOwnerUser])
def api_settle_payment(request):
    """
    Settles order bill, validates/redeems customer coupon, issues receipt,
    frees dining table, and prints customer receipt.
    """
    data = request.data
    order_id = data.get('order_id')
    payment_method = data.get('payment_method', 'cash').lower()
    ref_number = data.get('reference_number', '').strip()
    coupon_code = data.get('coupon_code', '').strip()
    customer_phone = data.get('customer_phone', '').strip()
    customer_email = data.get('customer_email', '').strip()

    if not order_id:
        return Response({'error': 'Order ID is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if payment_method not in ('cash', 'upi', 'card'):
        return Response({'error': 'Invalid payment method.'}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        order = Order.objects.select_for_update().filter(id=order_id).first()
        if not order:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)
        if order.is_paid:
            return Response({'error': f'Order {order.order_number} is already paid and settled.'}, status=status.HTTP_400_BAD_REQUEST)

        # Apply coupon if specified
        applied_coupon = None
        discount_amount = Decimal('0.00')

        if coupon_code:
            upper_code = coupon_code.upper()
            applied_coupon = (
                Coupon.objects.select_for_update().filter(code_plain__iexact=upper_code).first() or
                Coupon.objects.select_for_update().filter(code_hash=digest(upper_code)).first() or
                Coupon.objects.select_for_update().filter(code_hash=digest(coupon_code)).first()
            )
            if not applied_coupon and len(coupon_code) >= 4:
                possible = Coupon.objects.select_for_update().filter(code_hint__iexact=coupon_code[-4:], status='active')
                if possible.count() == 1:
                    applied_coupon = possible.first()

            if applied_coupon and applied_coupon.status == 'active':
                pct = Decimal(str(applied_coupon.percentage))
                raw_disc = (order.subtotal * (pct / Decimal('100.00'))).quantize(Decimal('0.01'))
                discount_amount = min(raw_disc, Decimal(str(applied_coupon.max_discount)))

                applied_coupon.status = 'redeemed'
                applied_coupon.save(update_fields=['status'])

                # Record core Redemption
                Redemption.objects.create(
                    coupon=applied_coupon,
                    staff=request.user,
                    bill_amount=order.subtotal,
                    discount_amount=discount_amount
                )

                order.coupon = applied_coupon
                order.coupon_code = applied_coupon.code_plain or f"RAYA-*{applied_coupon.code_hint}"

        # Link or create customer record for digital bill access
        resolved_customer = None
        if customer_email:
            resolved_customer, _ = Customer.objects.get_or_create(email=customer_email.strip().lower())
            if customer_phone and not resolved_customer.phone_number:
                resolved_customer.phone_number = customer_phone
                resolved_customer.save(update_fields=['phone_number'])
        elif customer_phone:
            resolved_customer = Customer.objects.filter(phone_number=customer_phone).first()

        if resolved_customer:
            order.customer = resolved_customer
            if customer_phone:
                order.customer_phone = customer_phone
            if not order.customer_name and customer_email:
                order.customer_name = customer_email.split('@')[0].capitalize()

        # Recalculate totals with discount applied
        order.recalculate_totals(apply_discount_amount=discount_amount)

        # Create Payment
        payment = Payment.objects.create(
            order=order,
            amount=order.grand_total,
            payment_method=payment_method,
            reference_number=ref_number,
            received_by=request.user
        )

        # Generate Receipt with retry on collision
        receipt = None
        for attempt in range(5):
            receipt_num = Receipt.generate_next_receipt_number()
            try:
                with transaction.atomic():
                    receipt = Receipt.objects.create(
                        receipt_number=receipt_num,
                        order=order,
                        subtotal=order.subtotal,
                        discount_amount=order.discount_amount,
                        tax_amount=order.tax_amount,
                        grand_total=order.grand_total,
                        payment_method=payment_method,
                        issued_by=request.user
                    )
                break
            except Exception:
                if attempt == 4:
                    raise

        # Mark Order paid & completed
        order.is_paid = True
        order.status = 'completed'
        order.save(update_fields=['is_paid', 'status', 'customer', 'customer_phone', 'customer_name', 'coupon', 'coupon_code'])

        # Free table if Dine-in
        if order.table:
            order.table.status = 'available'
            order.table.save(update_fields=['status'])

        # Format and queue counter receipt print job
        receipt_preview, _ = format_receipt_ticket(receipt, is_reprint=False)
        job = PrintJob.objects.create(
            idempotency_key=f"RCP-{receipt.receipt_number}",
            printer_type='billing',
            job_type='bill_receipt',
            order=order,
            content=receipt_preview
        )
        dispatch_print_job(job)

        AuditLog.objects.create(
            user=request.user,
            action='bill_settled',
            entity_type='receipt',
            entity_id=str(receipt.id),
            details=f"Order {order.order_number} settled with {payment_method.upper()} for ₹{order.grand_total}. Receipt: {receipt.receipt_number}",
            ip_address=request.META.get('REMOTE_ADDR', '')
        )

        return Response({
            'success': True,
            'message': f'Bill #{receipt.receipt_number} settled successfully!',
            'receipt': {
                'receipt_number': receipt.receipt_number,
                'order_number': order.order_number,
                'subtotal': str(receipt.subtotal),
                'discount_amount': str(receipt.discount_amount),
                'tax_amount': str(receipt.tax_amount),
                'grand_total': str(receipt.grand_total),
                'payment_method': receipt.payment_method,
                'issued_at': receipt.issued_at.isoformat(),
                'text_preview': receipt_preview
            }
        })


@api_view(['POST'])
@permission_classes([IsStaffOrOwnerUser])
def api_reprint_bill(request):
    """
    Reprints customer bill receipt marked as DUPLICATE.
    """
    order_id = request.data.get('order_id')
    receipt_id = request.data.get('receipt_id')

    receipt = None
    if receipt_id:
        receipt = Receipt.objects.filter(id=receipt_id).first()
    elif order_id:
        receipt = Receipt.objects.filter(order_id=order_id).first()

    if not receipt:
        return Response({'error': 'Receipt not found.'}, status=status.HTTP_404_NOT_FOUND)

    receipt.is_reprint = True
    receipt.reprint_count += 1
    receipt.save(update_fields=['is_reprint', 'reprint_count'])

    preview_text, _ = format_receipt_ticket(receipt, is_reprint=True)
    job = PrintJob.objects.create(
        idempotency_key=f"REPRINT-RCP-{receipt.id}-{timezone.now().timestamp()}",
        printer_type='billing',
        job_type='reprint_bill',
        order=receipt.order,
        content=preview_text
    )
    dispatch_print_job(job)

    return Response({
        'success': True,
        'message': f"Duplicate receipt for #{receipt.receipt_number} queued for printing.",
        'reprint_count': receipt.reprint_count
    })


# ==============================================================================
# CUSTOMER DIGITAL BILLS API
# ==============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def api_customer_bills(request):
    """
    Returns digital receipts for the logged-in customer (or matching email/phone).
    Enables customers to view and download their bills on mobile after QR login.
    """
    from core.views import get_customer

    customer = get_customer(request)
    email = request.GET.get('email', '').strip().lower()
    phone = request.GET.get('phone', '').strip()

    if customer:
        email = customer.email
        phone = customer.phone_number or phone

    if not email and not phone:
        return Response({'error': 'Please provide email or log in to view receipts.'}, status=status.HTTP_401_UNAUTHORIZED)

    q = Q()
    if email:
        q |= Q(order__customer__email__iexact=email) | Q(order__customer_name__icontains=email)
    if phone:
        q |= Q(order__customer_phone=phone)

    receipts = Receipt.objects.filter(q).order_by('-issued_at')[:20]

    result = []
    for r in receipts:
        items = []
        for it in r.order.items.filter(is_cancelled=False):
            items.append({
                'name': it.product_name,
                'qty': it.quantity,
                'price': str(it.unit_price),
                'total': str(it.line_total)
            })
        result.append({
            'receipt_number': r.receipt_number,
            'order_number': r.order.order_number,
            'order_type': r.order.get_order_type_display(),
            'table': r.order.table.number if r.order.table else None,
            'date': timezone.localtime(r.issued_at).strftime('%d %b %Y, %I:%M %p'),
            'subtotal': str(r.subtotal),
            'discount': str(r.discount_amount),
            'coupon_code': r.order.coupon_code,
            'tax': str(r.tax_amount),
            'grand_total': str(r.grand_total),
            'payment_method': r.payment_method.upper(),
            'items': items
        })
    return Response(result)


# ==============================================================================
# OWNER ADMIN METRICS & MANAGEMENT APIs
# ==============================================================================

@api_view(['GET'])
@permission_classes([IsOwnerUser])
def api_admin_metrics(request):
    """
    Returns live restaurant KPIs for owner dashboard.
    """
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_payments = Payment.objects.filter(created_at__gte=today_start)

    today_sales = today_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    cash_sales = today_payments.filter(payment_method='cash').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    upi_sales = today_payments.filter(payment_method='upi').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    card_sales = today_payments.filter(payment_method='card').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    today_orders_count = Order.objects.filter(created_at__gte=today_start).count()
    active_tables_count = DiningTable.objects.filter(status='occupied').count()
    total_tables_count = DiningTable.objects.filter(is_active=True).count()
    pending_kitchen_jobs = PrintJob.objects.filter(status='pending', printer_type='kitchen').count()

    total_discounts = Receipt.objects.filter(issued_at__gte=today_start).aggregate(total=Sum('discount_amount'))['total'] or Decimal('0.00')

    return Response({
        'today_sales': str(today_sales),
        'cash_sales': str(cash_sales),
        'upi_sales': str(upi_sales),
        'card_sales': str(card_sales),
        'today_orders_count': today_orders_count,
        'active_tables': active_tables_count,
        'total_tables': total_tables_count,
        'pending_kitchen_jobs': pending_kitchen_jobs,
        'total_discounts_given': str(total_discounts)
    })


@api_view(['GET'])
@permission_classes([IsOwnerUser])
def api_admin_sales_report(request):
    """
    Returns detailed sales report breakdown by date and item.
    """
    period = request.GET.get('period', 'today')
    now = timezone.now()

    if period == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == '7days':
        start_date = now - timedelta(days=7)
    elif period == '30days':
        start_date = now - timedelta(days=30)
    else:
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

    receipts = Receipt.objects.filter(issued_at__gte=start_date).order_by('-issued_at')
    total_revenue = receipts.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
    total_bills = receipts.count()

    # Best selling products
    item_stats = (
        OrderItem.objects
        .filter(order__receipt__issued_at__gte=start_date, is_cancelled=False)
        .values('product_name')
        .annotate(total_qty=Sum('quantity'), total_rev=Sum('line_total'))
        .order_by('-total_qty')[:10]
    )

    top_items = [
        {
            'name': it['product_name'],
            'quantity': it['total_qty'],
            'revenue': str(it['total_rev'])
        }
        for it in item_stats
    ]

    return Response({
        'period': period,
        'total_revenue': str(total_revenue),
        'total_bills': total_bills,
        'top_items': top_items
    })


@api_view(['POST'])
@permission_classes([IsOwnerUser])
def api_admin_toggle_product(request):
    """
    Toggles menu item stock availability (Available <-> Out of Stock).
    """
    prod_id = request.data.get('product_id')
    product = Product.objects.filter(id=prod_id).first()
    if not product:
        return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

    product.is_available = not product.is_available
    product.save(update_fields=['is_available'])

    return Response({
        'success': True,
        'product_id': product.id,
        'is_available': product.is_available,
        'message': f"'{product.name}' is now {'Available' if product.is_available else 'Out of Stock'}."
    })


@api_view(['POST'])
@permission_classes([IsOwnerUser])
def api_admin_save_product(request):
    """
    Creates or updates a food item's price and details.
    """
    data = request.data
    prod_id = data.get('id')
    name = data.get('name', '').strip()
    category_id = data.get('category_id')
    price = data.get('price')

    if not name or not category_id or not price:
        return Response({'error': 'Name, category, and price are required.'}, status=status.HTTP_400_BAD_REQUEST)

    category = Category.objects.filter(id=category_id).first()
    if not category:
        return Response({'error': 'Category not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        price_val = Decimal(str(price))
    except Exception:
        return Response({'error': 'Invalid price amount.'}, status=status.HTTP_400_BAD_REQUEST)

    if prod_id:
        product = Product.objects.filter(id=prod_id).first()
        if not product:
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)
        product.name = name
        product.category = category
        product.price = price_val
        product.description = data.get('description', product.description)
        product.save()
    else:
        product = Product.objects.create(
            name=name,
            category=category,
            price=price_val,
            description=data.get('description', '')
        )

    return Response({
        'success': True,
        'product': {
            'id': product.id,
            'name': product.name,
            'price': str(product.price),
            'category_name': category.name
        }
    })


@api_view(['POST'])
@permission_classes([IsOwnerUser])
def api_admin_test_print(request):
    """
    Sends a test print ticket to the TVS kitchen or billing printer.
    """
    printer_type = request.data.get('printer_type', 'kitchen')
    cfg = PrinterConfiguration.objects.filter(printer_type=printer_type).first()
    if not cfg:
        return Response({'error': f'Printer {printer_type} is not configured.'}, status=status.HTTP_404_NOT_FOUND)

    dummy_order = Order.objects.first()
    if not dummy_order:
        dummy_order = Order.objects.create(
            order_number='TEST-001',
            order_type='dine_in',
            created_by=request.user
        )

    test_content = (
        f"==========================================\n"
        f"         RAYARA CAFE - TEST PRINT         \n"
        f"==========================================\n"
        f"Printer: {cfg.name}\n"
        f"Target:  {cfg.get_printer_type_display()}\n"
        f"Mode:    {cfg.get_connection_type_display()}\n"
        f"Device:  {cfg.device_identifier} (Port {cfg.port})\n"
        f"Time:    {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Status:  PRINTER HARDWARE OPERATIONAL\n"
        f"==========================================\n"
    )

    job = PrintJob.objects.create(
        idempotency_key=f"TEST-{printer_type}-{uuid.uuid4().hex[:8]}",
        printer_type=printer_type,
        job_type='new_order',
        order=dummy_order,
        content=test_content
    )

    success = dispatch_print_job(job)

    return Response({
        'success': success,
        'job_id': job.id,
        'status': job.status,
        'error_message': job.error_message,
        'preview': test_content
    })

