import json
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .permissions import (
    is_owner, is_staff_member,
    owner_required, staff_required
)
from .models import (
    BusinessSettings, DiningTable, Category, Product,
    TaxConfiguration, Discount, Order, OrderItem,
    PrinterConfiguration, PrintJob, Payment, Receipt, AuditLog
)


def pos_status(request):
    """
    Phase 1 POS system status and environment check.
    """
    return JsonResponse({
        'system': 'Rayara Cafe Restaurant POS & Management System',
        'status': 'online',
        'version': '1.0.0',
        'phase': 1,
        'authenticated_user': request.user.username if request.user.is_authenticated else None,
        'role': 'owner' if is_owner(request.user) else ('staff' if is_staff_member(request.user) else None),
        'modules': [
            'database_architecture',
            'authentication_rbac',
            'admin_dashboard',
            'staff_tablet_ordering',
            'order_apis',
            'kitchen_print_queue',
            'additional_orders_cancellations',
            'billing_receipt_printing',
            'sales_reports_analytics'
        ]
    })


@csrf_protect
def pos_login(request):
    """
    General login router: redirects to Staff Login or Owner Login.
    """
    if request.user.is_authenticated:
        if is_owner(request.user):
            return redirect('/pos/admin/')
        return redirect('/pos/tablet/')
    return redirect('pos:staff_login')


@csrf_protect
def staff_login(request):
    """
    Dedicated Login Portal for Staff & Cashiers.
    Strictly forbids customers and normal unprivileged accounts.
    """
    if request.user.is_authenticated:
        if is_staff_member(request.user):
            return redirect('/pos/tablet/')
        logout(request)

    next_url = request.GET.get('next') or request.POST.get('next') or ''

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                messages.error(request, "This staff account has been deactivated.")
                return render(request, 'pos/staff_login.html', {'next': next_url})

            if not is_staff_member(user):
                messages.error(request, "Access Denied: Only authorized staff and cashiers can sign in here.")
                return render(request, 'pos/staff_login.html', {'next': next_url})

            login(request, user)
            AuditLog.objects.create(
                user=user,
                action='staff_login',
                entity_type='user',
                entity_id=str(user.id),
                details=f"Staff member {user.username} logged into tablet/counter",
                ip_address=request.META.get('REMOTE_ADDR', '')
            )
            if next_url and next_url.startswith('/pos/'):
                return redirect(next_url)
            if user.username == 'kitchen':
                return redirect('/pos/kitchen/')
            return redirect('/pos/tablet/')
        else:
            messages.error(request, "Invalid staff username or password.")

    return render(request, 'pos/staff_login.html', {'next': next_url})


@csrf_protect
def owner_login(request):
    """
    Dedicated Master Login Portal for Restaurant Owner / Administrator.
    Strictly enforces superuser authentication; rejects staff and customer accounts.
    """
    if request.user.is_authenticated:
        if is_owner(request.user):
            return redirect('/pos/admin/')
        logout(request)

    next_url = request.GET.get('next') or request.POST.get('next') or ''

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                messages.error(request, "This owner account has been deactivated.")
                return render(request, 'pos/owner_login.html', {'next': next_url})

            if not is_owner(user):
                messages.error(
                    request,
                    "Access Denied: Owner administrator privileges required for this portal. "
                    "Staff and Cashiers please use the Staff Portal."
                )
                return render(request, 'pos/owner_login.html', {'next': next_url})

            login(request, user)
            AuditLog.objects.create(
                user=user,
                action='owner_login',
                entity_type='user',
                entity_id=str(user.id),
                details=f"Owner {user.username} logged into executive admin dashboard",
                ip_address=request.META.get('REMOTE_ADDR', '')
            )
            if next_url and next_url.startswith('/pos/'):
                return redirect(next_url)
            return redirect('/pos/admin/')
        else:
            messages.error(request, "Invalid owner username or master password.")

    return render(request, 'pos/owner_login.html', {'next': next_url})


def pos_logout(request):
    """
    Log out active user and redirect to appropriate portal.
    """
    was_owner = is_owner(request.user) if request.user.is_authenticated else False
    if request.user.is_authenticated:
        AuditLog.objects.create(
            user=request.user,
            action='user_logout',
            entity_type='user',
            entity_id=str(request.user.id),
            details=f"User {request.user.username} logged out from POS",
            ip_address=request.META.get('REMOTE_ADDR', '')
        )
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('pos:owner_login' if was_owner else 'pos:staff_login')


@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    """
    JSON API login endpoint for tablet app or AJAX clients.
    """
    data = request.data
    username = data.get('username', '').strip()
    password = data.get('password', '')

    user = authenticate(request, username=username, password=password)
    if user is not None:
        if not user.is_active:
            return Response({'error': 'Account deactivated.'}, status=status.HTTP_403_FORBIDDEN)
        login(request, user)
        return Response({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_owner': is_owner(user),
                'is_staff': is_staff_member(user),
            },
            'redirect': '/pos/admin/' if is_owner(user) else '/pos/tablet/'
        })
    return Response({'error': 'Invalid username or password.'}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_me(request):
    """
    Returns current authenticated session user and permissions.
    """
    user = request.user
    return Response({
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_owner': is_owner(user),
        'is_staff': is_staff_member(user),
    })


@staff_required
def tablet_dashboard(request):
    """
    Staff Tablet Ordering Interface (Phase 5).
    """
    return render(request, 'pos/tablet.html', {
        'user': request.user,
        'is_owner': is_owner(request.user),
        'settings': BusinessSettings.get_settings(),
    })


@staff_required
def billing_counter(request):
    """
    Billing Counter System (Phase 9).
    """
    return render(request, 'pos/billing.html', {
        'user': request.user,
        'is_owner': is_owner(request.user),
        'settings': BusinessSettings.get_settings(),
    })


@owner_required
def owner_dashboard(request):
    """
    Owner Admin Dashboard & Analytics (Phase 4 & Phase 10).
    """
    return render(request, 'pos/admin.html', {
        'user': request.user,
        'settings': BusinessSettings.get_settings(),
    })


@staff_required
@ensure_csrf_cookie
def kitchen_dashboard(request):
    """
    Kitchen Display System (KDS) Screen (Phase 6 / Tablet KOT Screen).
    Receives live order tickets, sound chimes, and preparation updates.
    """
    return render(request, 'pos/kitchen.html', {
        'user': request.user,
        'is_owner': is_owner(request.user),
        'settings': BusinessSettings.get_settings(),
    })


@csrf_protect
def kitchen_login(request):
    """
    Dedicated Login Portal for Kitchen Staff & Chefs.
    """
    if request.user.is_authenticated:
        if is_staff_member(request.user):
            return redirect('/pos/kitchen/')
        logout(request)

    next_url = request.GET.get('next') or request.POST.get('next') or '/pos/kitchen/'

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                messages.error(request, "This kitchen account has been deactivated.")
                return render(request, 'pos/kitchen_login.html', {'next': next_url})

            if not is_staff_member(user):
                messages.error(request, "Access Denied: Staff or Kitchen privileges required.")
                return render(request, 'pos/kitchen_login.html', {'next': next_url})

            login(request, user)
            AuditLog.objects.create(
                user=user,
                action='kitchen_login',
                entity_type='user',
                entity_id=str(user.id),
                details=f"Kitchen staff {user.username} logged into Kitchen Display System",
                ip_address=request.META.get('REMOTE_ADDR', '')
            )
            return redirect(next_url if next_url.startswith('/pos/') else '/pos/kitchen/')
        else:
            messages.error(request, "Invalid kitchen username or password.")

    return render(request, 'pos/kitchen_login.html', {'next': next_url})
