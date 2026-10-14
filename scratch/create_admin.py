import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prime_hardware.settings')
django.setup()

from django.contrib.auth.models import User

username = 'Admin'
email = 'admin@example.com'
password = 'admin@123'

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print(f"Superuser '{username}' created successfully.")
else:
    user = User.objects.get(username=username)
    user.set_password(password)
    user.is_staff = True
    user.is_superuser = True
    user.save()
    print(f"Superuser '{username}' updated successfully.")
