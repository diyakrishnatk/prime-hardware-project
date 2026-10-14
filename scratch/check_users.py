import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prime_hardware.settings')
django.setup()

from django.contrib.auth.models import User

users = User.objects.all()
for user in users:
    print(f"Username: {user.username}, Is Staff: {user.is_staff}, Is Superuser: {user.is_superuser}")
