from django.urls import path
from . import views

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

    # Portals
    path('tablet/', views.tablet_dashboard, name='tablet'),
    path('billing/', views.billing_counter, name='billing'),
    path('admin/', views.owner_dashboard, name='owner_dashboard'),
]
