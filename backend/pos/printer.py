"""
Rayara Cafe - Thermal Printer & ESC/POS Print Engine
Supports TVS Thermal Printers, Windows Spooler drivers (win32print),
Ethernet RAW Sockets (Port 9100), and Simulated testing sinks.
"""

import os
import socket
import logging
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from .models import PrinterConfiguration, PrintJob, BusinessSettings

logger = logging.getLogger(__name__)

# --- ESC/POS Command Constants ---
ESC = b'\x1b'
GS = b'\x1d'
INIT_PRINTER = ESC + b'@'
ALIGN_LEFT = ESC + b'a\x00'
ALIGN_CENTER = ESC + b'a\x01'
ALIGN_RIGHT = ESC + b'a\x02'
BOLD_ON = ESC + b'E\x01'
BOLD_OFF = ESC + b'E\x00'
DOUBLE_HEIGHT = ESC + b'!\x10'
DOUBLE_WIDTH = ESC + b'!\x20'
DOUBLE_SIZE = ESC + b'!\x30'
NORMAL_SIZE = ESC + b'!\x00'
FEED_LINE = b'\n'
CUT_FULL = GS + b'V\x00'
CUT_PARTIAL = GS + b'V\x01'
CASH_DRAWER_KICK = ESC + b'p\x00\x19\xfa'  # Standard pulse pin 2


def get_receipt_dir():
    receipt_dir = os.path.join(settings.MEDIA_ROOT, 'receipts')
    os.makedirs(receipt_dir, exist_ok=True)
    return receipt_dir


def format_kitchen_ticket(order, items, job_type='new_order', batch_number=1, reason=''):
    """
    Renders a kitchen order ticket (KOT) optimized for 80mm thermal rolls.
    """
    width = 42
    divider = '-' * width
    double_divider = '=' * width

    # Header title
    if job_type == 'new_order':
        title = "*** KITCHEN ORDER (KOT) ***"
    elif job_type == 'additional_order':
        title = f"*** ADD-ON ORDER (BATCH #{batch_number}) ***"
    elif job_type == 'cancelled_item':
        title = "*** CANCELLED ITEM ALERT ***"
    elif job_type == 'reprint_kitchen':
        title = "*** KOT REPRINT ***"
    else:
        title = "*** KITCHEN TICKET ***"

    order_target = f"TABLE {order.table.number}" if order.order_type == 'dine_in' and order.table else "TAKEAWAY"
    now_str = timezone.localtime(timezone.now()).strftime('%d-%b-%Y  %I:%M %p')
    waiter = order.created_by.get_full_name() or order.created_by.username

    lines = [
        "RAYARA CAFE",
        title,
        double_divider,
        f"Order: {order.order_number:<15} {order_target:>20}",
        f"Server: {waiter:<14} {now_str:>20}",
    ]

    if order.order_type == 'takeaway' and order.customer_name:
        lines.append(f"Customer: {order.customer_name} ({order.customer_phone or 'No phone'})")
    if order.order_type == 'takeaway' and order.takeaway_notes:
        lines.append(f"Notes: {order.takeaway_notes}")

    if reason:
        lines.append(divider)
        lines.append(f"REASON: {reason}")

    lines.append(divider)
    lines.append(f"{'QTY':<5} {'ITEM DESCRIPTION':<28} {'BATCH':>7}")
    lines.append(divider)

    for item in items:
        status_tag = " [CANCELLED]" if item.is_cancelled else ""
        item_line = f"{item.quantity:<5} {item.product_name + status_tag:<28} {f'B#{item.batch_number}':>7}"
        lines.append(item_line)
        if item.special_instructions:
            lines.append(f"      >> NOTE: {item.special_instructions}")

    lines.append(double_divider)
    if job_type == 'additional_order':
        lines.append(">> PREPARE IMMEDIATELY FOR SAME TABLE <<")
    lines.append("")

    text_preview = "\n".join(lines)

    # Build ESC/POS bytes
    buf = bytearray()
    buf += INIT_PRINTER
    buf += ALIGN_CENTER
    buf += BOLD_ON
    buf += DOUBLE_SIZE
    buf += b"RAYARA CAFE\n"
    buf += NORMAL_SIZE
    buf += title.encode('utf-8') + b"\n"
    buf += BOLD_OFF
    buf += ALIGN_LEFT
    buf += double_divider.encode('ascii') + b"\n"
    buf += f"Order: {order.order_number}   {order_target}\n".encode('utf-8')
    buf += f"Time:  {now_str}   By: {waiter}\n".encode('utf-8')
    buf += divider.encode('ascii') + b"\n"

    for item in items:
        buf += BOLD_ON
        qty_name = f"{item.quantity}x {item.product_name}\n"
        buf += qty_name.encode('utf-8')
        buf += BOLD_OFF
        if item.special_instructions:
            buf += f"   * {item.special_instructions}\n".encode('utf-8')

    buf += double_divider.encode('ascii') + b"\n"
    buf += FEED_LINE * 4
    buf += CUT_PARTIAL

    return text_preview, bytes(buf)


def format_receipt_ticket(receipt, is_reprint=False):
    """
    Renders customer tax invoice / billing receipt with itemized totals,
    discounts, CGST/SGST taxes, and Rayara Cafe branding.
    """
    order = receipt.order
    biz = BusinessSettings.get_settings()
    width = 42
    divider = '-' * width
    double_divider = '=' * width

    now_str = timezone.localtime(receipt.issued_at).strftime('%d-%b-%Y  %I:%M %p')
    cashier = receipt.issued_by.get_full_name() or receipt.issued_by.username
    order_target = f"Table {order.table.number}" if order.order_type == 'dine_in' and order.table else "Takeaway"

    lines = [
        biz.cafe_name.center(width),
        biz.tagline.center(width),
        biz.address.center(width),
        f"Phone: {biz.phone}".center(width),
    ]
    if biz.gst_number:
        lines.append(f"GSTIN: {biz.gst_number}".center(width))
    if biz.fssai_license:
        lines.append(f"FSSAI Lic: {biz.fssai_license}".center(width))

    lines.append(double_divider)
    if is_reprint:
        lines.append("*** DUPLICATE / REPRINT RECEIPT ***".center(width))
    else:
        lines.append("*** TAX INVOICE ***".center(width))
    lines.append(double_divider)

    lines.append(f"Receipt #: {receipt.receipt_number:<16} Order: {order.order_number:>13}")
    lines.append(f"Type:      {order_target:<16} Date:  {now_str:>13}")
    lines.append(f"Cashier:   {cashier}")
    if order.customer_name or order.customer_phone:
        lines.append(f"Customer:  {order.customer_name or 'Valued Customer'} ({order.customer_phone or ''})")

    lines.append(divider)
    lines.append(f"{'ITEM':<22} {'QTY':>4} {'PRICE':>6} {'TOTAL':>8}")
    lines.append(divider)

    active_items = order.items.filter(is_cancelled=False)
    for it in active_items:
        name = it.product_name[:21]
        lines.append(f"{name:<22} {it.quantity:>4} {it.unit_price:>6.2f} {it.line_total:>8.2f}")

    lines.append(divider)
    lines.append(f"{'Subtotal:':<30} {biz.currency_symbol} {receipt.subtotal:>9.2f}")

    if receipt.discount_amount > Decimal('0.00'):
        coupon_str = f"Coupon ({order.coupon_code}):" if order.coupon_code else "Discount Applied:"
        lines.append(f"{coupon_str:<30} -{biz.currency_symbol} {receipt.discount_amount:>9.2f}")

    if receipt.tax_amount > Decimal('0.00'):
        half_tax = (receipt.tax_amount / Decimal('2.00')).quantize(Decimal('0.01'))
        lines.append(f"{'CGST (2.5%):':<30} {biz.currency_symbol} {half_tax:>9.2f}")
        lines.append(f"{'SGST (2.5%):':<30} {biz.currency_symbol} {half_tax:>9.2f}")

    lines.append(double_divider)
    lines.append(f"{'GRAND TOTAL:':<28} {biz.currency_symbol} {receipt.grand_total:>11.2f}")
    lines.append(double_divider)

    lines.append(f"Payment Mode: {receipt.payment_method.upper()}")
    latest_payment = order.payments.last()
    if latest_payment and latest_payment.reference_number:
        lines.append(f"Ref / UTR:    {latest_payment.reference_number}")

    lines.append("")
    for fline in biz.receipt_footer_text.splitlines():
        lines.append(fline.center(width))
    lines.append(double_divider)

    text_preview = "\n".join(lines)

    # Build ESC/POS bytes
    buf = bytearray()
    buf += INIT_PRINTER
    buf += ALIGN_CENTER
    buf += BOLD_ON
    buf += DOUBLE_SIZE
    buf += f"{biz.cafe_name}\n".encode('utf-8')
    buf += NORMAL_SIZE
    buf += f"{biz.address}\n".encode('utf-8')
    buf += f"Phone: {biz.phone}\n".encode('utf-8')
    buf += BOLD_OFF
    buf += double_divider.encode('ascii') + b"\n"
    buf += b"*** TAX INVOICE ***\n"
    buf += ALIGN_LEFT
    buf += f"Receipt: {receipt.receipt_number}  Order: {order.order_number}\n".encode('utf-8')
    buf += f"Date: {now_str}\n".encode('utf-8')
    buf += divider.encode('ascii') + b"\n"

    for it in active_items:
        buf += f"{it.product_name[:20]:<20} {it.quantity:>3}x {it.line_total:>8.2f}\n".encode('utf-8')

    buf += divider.encode('ascii') + b"\n"
    buf += f"Subtotal:    Rs. {receipt.subtotal:.2f}\n".encode('ascii')
    if receipt.discount_amount > Decimal('0.00'):
        buf += f"Discount:   -Rs. {receipt.discount_amount:.2f}\n".encode('ascii')
    buf += f"Tax:         Rs. {receipt.tax_amount:.2f}\n".encode('ascii')
    buf += BOLD_ON
    buf += DOUBLE_HEIGHT
    buf += f"TOTAL:       Rs. {receipt.grand_total:.2f}\n".encode('ascii')
    buf += NORMAL_SIZE
    buf += BOLD_OFF
    buf += double_divider.encode('ascii') + b"\n"
    buf += ALIGN_CENTER
    buf += b"Thank You! Visit Again\n"
    buf += FEED_LINE * 4
    buf += CUT_FULL
    buf += CASH_DRAWER_KICK

    return text_preview, bytes(buf)


def send_to_windows_spooler(printer_name: str, raw_bytes: bytes, job_title="Rayara Print Ticket") -> tuple[bool, str]:
    """
    Sends raw ESC/POS binary data to a Windows thermal printer driver (USB) via pywin32.
    """
    try:
        import win32print
        p = win32print.OpenPrinter(printer_name)
        try:
            job = win32print.StartDocPrinter(p, 1, (job_title, None, "RAW"))
            win32print.StartPagePrinter(p)
            win32print.WritePrinter(p, raw_bytes)
            win32print.EndPagePrinter(p)
            win32print.EndDocPrinter(p)
            return True, f"Printed successfully via Windows Spooler [{printer_name}]"
        finally:
            win32print.ClosePrinter(p)
    except Exception as e:
        logger.error(f"Windows Spooler printing failed for {printer_name}: {e}")
        return False, str(e)


def send_to_network_socket(host: str, port: int, raw_bytes: bytes, timeout=4) -> tuple[bool, str]:
    """
    Sends raw ESC/POS binary data to an Ethernet/Wi-Fi thermal printer socket (Port 9100).
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
            s.sendall(raw_bytes)
            return True, f"Printed successfully via Network RAW Socket [{host}:{port}]"
    except Exception as e:
        logger.error(f"Network socket printing failed for {host}:{port}: {e}")
        return False, str(e)


def dispatch_print_job(job: PrintJob) -> bool:
    """
    Dispatches a single PrintJob based on printer configuration.
    Returns True if successfully dispatched or simulated, False otherwise.
    """
    cfg = PrinterConfiguration.objects.filter(printer_type=job.printer_type, is_active=True).first()
    conn_type = cfg.connection_type if cfg else 'simulated'
    device = cfg.device_identifier if cfg else 'virtual'
    port = cfg.port if cfg else 9100

    job.attempts += 1
    job.locked_at = timezone.now()
    job.status = 'processing'
    job.save(update_fields=['attempts', 'locked_at', 'status'])

    # Prepare preview save in media directory
    receipt_dir = get_receipt_dir()
    filepath = os.path.join(receipt_dir, f"job_{job.id}_{job.printer_type}_{job.order.order_number}.txt")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(job.content)

    success = False
    msg = ""

    if conn_type == 'simulated':
        success = True
        msg = f"Simulated printer output saved to {filepath}"
    elif conn_type == 'usb_spooler':
        # Generate raw bytes from content or reformat
        _, raw_bytes = (
            format_receipt_ticket(job.order.receipt)
            if job.job_type in ('bill_receipt', 'reprint_bill') and hasattr(job.order, 'receipt')
            else format_kitchen_ticket(job.order, job.order.items.all(), job_type=job.job_type)
        )
        success, msg = send_to_windows_spooler(device, raw_bytes, f"Rayara-{job.id}")
        if not success:
            # Fall back to simulated write so restaurant workflow does not crash
            logger.warning(f"Fallback to simulation for job #{job.id}: {msg}")
    elif conn_type == 'ethernet':
        _, raw_bytes = (
            format_receipt_ticket(job.order.receipt)
            if job.job_type in ('bill_receipt', 'reprint_bill') and hasattr(job.order, 'receipt')
            else format_kitchen_ticket(job.order, job.order.items.all(), job_type=job.job_type)
        )
        success, msg = send_to_network_socket(device, port, raw_bytes)
    else:
        success = True
        msg = f"Completed in dummy mode ({conn_type})"

    if success:
        job.status = 'printed'
        job.printed_at = timezone.now()
        job.error_message = msg
        job.save(update_fields=['status', 'printed_at', 'error_message'])
        return True
    else:
        if job.attempts >= job.max_attempts:
            job.status = 'failed'
        else:
            job.status = 'pending'
        job.error_message = msg
        job.save(update_fields=['status', 'error_message'])
        return False


def process_pending_print_jobs(limit=10) -> int:
    """
    Worker utility that processes pending print jobs with transactional locking.
    """
    from django.db import transaction

    processed = 0
    with transaction.atomic():
        pending_jobs = list(
            PrintJob.objects.select_for_update(skip_locked=True)
            .filter(status='pending', attempts__lt=3)
            .order_by('created_at')[:limit]
        )
        for job in pending_jobs:
            if dispatch_print_job(job):
                processed += 1
    return processed

