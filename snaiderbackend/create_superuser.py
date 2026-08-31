import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'snaiderbackend.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

if not password:
    raise RuntimeError(
        'Falta la variable DJANGO_SUPERUSER_PASSWORD. ' 
        'Definila en Render o en tu entorno.'
    )

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f'Superuser created: {username}')
else:
    print(f'Superuser already exists: {username}')
