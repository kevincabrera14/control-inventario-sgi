from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
import os
from django.http import HttpResponse
from django.shortcuts import render

def service_worker(request):
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'sw.js')
    try:
        with open(sw_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        return HttpResponse('/* Service worker not found */', content_type='application/javascript')
    return HttpResponse(content, content_type='application/javascript')


def offline_view(request):
    return render(request, 'pwa/offline.html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('app.urls')),
    path('sw.js', service_worker, name='service_worker'),
    path('offline/', offline_view, name='offline'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
