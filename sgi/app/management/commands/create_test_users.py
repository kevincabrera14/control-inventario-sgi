from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group

class Command(BaseCommand):
    help = 'Crea usuarios de prueba y los asigna a los grupos requeridos para SGI.'

    def handle(self, *args, **options):
        # Definir grupos requeridos
        groups = ['Administrador', 'Bodeguero', 'Gerente']
        for grp_name in groups:
            group, created = Group.objects.get_or_create(name=grp_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Grupo '{grp_name}' creado."))
            else:
                self.stdout.write(f"Grupo '{grp_name}' ya existía.")

        # Definir usuarios de prueba
        users_data = [
            {
                'username': 'admin',
                'password': 'admin123',
                'email': 'admin@example.com',
                'is_staff': True,
                'is_superuser': True,
                'groups': ['Administrador', 'Gerente'],
            },
            {
                'username': 'bodeguero',
                'password': 'bodeguero123',
                'email': 'bodeguero@example.com',
                'is_staff': False,
                'is_superuser': False,
                'groups': ['Bodeguero'],
            },
            {
                'username': 'gerente',
                'password': 'gerente123',
                'email': 'gerente@example.com',
                'is_staff': False,
                'is_superuser': False,
                'groups': ['Gerente'],
            },
        ]

        for udata in users_data:
            username = udata['username']
            if User.objects.filter(username=username).exists():
                self.stdout.write(f"Usuario '{username}' ya existía, se omite.")
                continue
            user = User.objects.create_user(
                username=username,
                password=udata['password'],
                email=udata['email'],
                is_staff=udata['is_staff'],
                is_superuser=udata['is_superuser'],
            )
            # Asignar grupos
            for grp_name in udata['groups']:
                group = Group.objects.get(name=grp_name)
                user.groups.add(group)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Usuario '{username}' creado y asignado a grupos: {', '.join(udata['groups'])}."))
