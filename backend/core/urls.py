from django.urls import re_path
from . import views

urlpatterns = [
    # Customer Auth & OTP
    re_path(r'^customer/send-otp/?$', views.send_otp),
    re_path(r'^customer/verify-otp/?$', views.verify_otp),
    re_path(r'^customer/me/?$', views.customer_me),
    re_path(r'^customer/logout/?$', views.customer_logout),

    # Café Menu & Games
    re_path(r'^menu/?$', views.menu),
    re_path(r'^games/?$', views.games),
    re_path(r'^game/play/?$', views.play),
    re_path(r'^coupons/?$', views.my_coupons),
    re_path(r'^customer/bills/?$', views.customer_bills if hasattr(views, 'customer_bills') else __import__('pos.api_views', fromlist=['api_customer_bills']).api_customer_bills),

    # Staff & Admin
    re_path(r'^staff/redeem/?$', views.redeem),
    re_path(r'^admin/dashboard/?$', views.dashboard),
]
