from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('django-admin/', RedirectView.as_view(url='/admin/', permanent=True)),
    path('api/', include('core.urls')),
    path('pos/', include('pos.urls', namespace='pos')),
    path('', RedirectView.as_view(url='/pos/status/', permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
