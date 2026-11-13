from django.urls import path
from . import views, api_views

app_name = 'pos'

urlpatterns = [
    # Status
    path('status/', views.pos_status, name='status'),

    # Dedicated Authentication Portals
    path('login/', views.pos_login, name='login'),
    path('staff/login/', views.staff_login, name='staff_login'),
    path('admin/login/', views.owner_login, name='owner_login'),
    path('logout/', views.pos_logout, name='logout'),
    path('api/auth/login/', views.api_login, name='api_login'),
    path('api/auth/me/', views.api_me, name='api_me'),

    # HTML Portals
    path('tablet/', views.tablet_dashboard, name='tablet'),
    path('kitchen/', views.kitchen_dashboard, name='kitchen_dashboard'),
    path('kitchen/login/', views.kitchen_login, name='kitchen_login'),
    path('billing/', views.billing_counter, name='billing'),
    path('admin/', views.owner_dashboard, name='owner_dashboard'),

    # Tablet & Kitchen Display APIs
    path('api/tables/', api_views.api_tables, name='api_tables'),
    path('api/menu/', api_views.api_menu, name='api_menu'),
    path('api/orders/create/', api_views.api_order_create, name='api_order_create'),
    path('api/orders/add-items/', api_views.api_order_add_items, name='api_order_add_items'),
    path('api/orders/cancel-item/', api_views.api_order_cancel_item, name='api_order_cancel_item'),
    path('api/orders/active/', api_views.api_active_orders, name='api_active_orders'),
    path('api/kitchen/orders/', api_views.api_kitchen_orders, name='api_kitchen_orders'),
    path('api/kitchen/orders/update-status/', api_views.api_kitchen_update_status, name='api_kitchen_update_status'),

    # Billing APIs
    path('api/billing/validate-coupon/', api_views.api_validate_coupon, name='api_validate_coupon'),
    path('api/billing/settle-payment/', api_views.api_settle_payment, name='api_settle_payment'),
    path('api/billing/reprint-bill/', api_views.api_reprint_bill, name='api_reprint_bill'),

    # Customer Digital Bills
    path('api/customer/bills/', api_views.api_customer_bills, name='api_customer_bills'),

    # Owner Admin APIs
    path('api/admin/metrics/', api_views.api_admin_metrics, name='api_admin_metrics'),
    path('api/admin/sales-report/', api_views.api_admin_sales_report, name='api_admin_sales_report'),
    path('api/admin/menu/product/toggle/', api_views.api_admin_toggle_product, name='api_admin_toggle_product'),
    path('api/admin/menu/product/save/', api_views.api_admin_save_product, name='api_admin_save_product'),
    path('api/admin/printer/test/', api_views.api_admin_test_print, name='api_admin_test_print'),
]
