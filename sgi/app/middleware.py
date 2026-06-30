from django.contrib.auth import login
from django.contrib.auth.models import AnonymousUser

from .models import DispositivoRecordado


DEVICE_COOKIE_NAME = 'sgi_device_token'


class DispositivoRecordadoMiddleware:
    """
    Si el usuario NO tiene sesión activa pero el navegador trae la cookie
    'sgi_device_token' con un token válido, lo loguea automáticamente
    antes de procesar la vista. Así, una vez que alguien entró en un
    dispositivo, queda recordado ahí permanentemente (incluso después
    de hacer logout), hasta que se borre la cookie manualmente.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated or isinstance(request.user, AnonymousUser):
            token = request.COOKIES.get(DEVICE_COOKIE_NAME)
            if token:
                try:
                    dispositivo = DispositivoRecordado.objects.select_related('user').get(token=token)
                    if dispositivo.user.is_active:
                        login(request, dispositivo.user)
                        dispositivo.save(update_fields=['ultimo_uso'])  # refresca 'ultimo_uso' (auto_now)
                except DispositivoRecordado.DoesNotExist:
                    pass  # token inválido o revocado: se ignora, no rompe la request

        response = self.get_response(request)
        return response