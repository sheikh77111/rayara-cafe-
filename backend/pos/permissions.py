from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from rest_framework import permissions


def is_owner(user):
    """Returns True if the user is an owner/administrator."""
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name='Owner').exists())


def is_staff_member(user):
    """Returns True if the user is a staff member or cashier or owner."""
    return user.is_authenticated and (user.is_staff or user.is_superuser or user.groups.filter(name='Staff').exists())


def owner_required(view_func):
    """
    Decorator for views accessible ONLY to verified Owners/Superusers.
    Strictly forbids staff, cashiers, customers, and anonymous users.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/pos/admin/login/?next={request.path}")
        if not is_owner(request.user):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.path.startswith('/pos/api/'):
                return JsonResponse({'error': 'Access Denied: Owner authorization required.'}, status=403)
            messages.error(request, "Access Denied: Owner administrator privileges required for this portal.")
            return redirect('/pos/tablet/')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def staff_required(view_func):
    """
    Decorator for views accessible to Staff, Cashiers, and Owners.
    Strictly blocks customers and unauthenticated users.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/pos/staff/login/?next={request.path}")
        if not is_staff_member(request.user):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.path.startswith('/pos/api/'):
                return JsonResponse({'error': 'Access Denied: Staff/Cashier authorization required.'}, status=403)
            messages.error(request, "Access Denied: Staff/Cashier login required.")
            return redirect('/pos/staff/login/')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# DRF API Permission Classes
class IsOwnerUser(permissions.BasePermission):
    """Allows access only to authenticated Owner administrators."""
    def has_permission(self, request, view):
        return is_owner(request.user)


class IsStaffOrOwnerUser(permissions.BasePermission):
    """Allows access to authenticated Staff, Cashiers, and Owners."""
    def has_permission(self, request, view):
        return is_staff_member(request.user)
