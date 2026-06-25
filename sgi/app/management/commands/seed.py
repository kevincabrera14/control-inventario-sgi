from django.core.management.base import BaseCommand
from django.core import management

class Command(BaseCommand):
    help = 'Carga fixtures de ejemplo para el proyecto SGI'

    def handle(self, *args, **options):
        self.stdout.write('Cargando fixtures...')
        try:
            management.call_command('loaddata', 'fixtures.json')
            self.stdout.write(self.style.SUCCESS('Fixtures cargados correctamente.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al cargar fixtures: {e}'))
