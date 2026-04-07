from pathlib import Path

# 1️⃣ Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# 2️⃣ Security
SECRET_KEY = 'django-insecure-REPLACE_THIS_WITH_A_SECRET_KEY'

# Robust Security for Local Development
DEBUG = True
ALLOWED_HOSTS = ['*']

# CSRF SETTINGS (Dedicated cookie mode for maximum reliability)
CSRF_USE_SESSIONS = False
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_NAME = 'prime_final_session'
CSRF_COOKIE_NAME = 'prime_final_csrf'

# Relax flags to avoid browser-side blocking on HTTP
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_HTTPONLY = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'

CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1',
    'http://localhost',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'http://0.0.0.0:8000',
    'http://0.0.0.0',
]

# 3️⃣ Installed apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Your App
    'shop',
]

# 4️⃣ Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# 5️⃣ Root URL
ROOT_URLCONF = 'prime_hardware.urls'

# 6️⃣ Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # global templates folder
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'shop.context_processors.cart_renderer',
            ],
        },
    },
]

# 7️⃣ WSGI
WSGI_APPLICATION = 'prime_hardware.wsgi.application'

# 8️⃣ Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# 9️⃣ Password validators
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# 10️⃣ Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# 11️⃣ Static files (CSS, JS, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / "static",  # your global static folder
]

# 12️⃣ Media files (Product images)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# 13️⃣ Default primary key field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


LOGIN_REDIRECT_URL = '/admin-dashboard/'
LOGOUT_REDIRECT_URL = '/'


MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_URL = '/signin/'



EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = 'diyakrishnatk@gmail.com'
EMAIL_HOST_PASSWORD = 'nhcvesrukyixttmh'

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

RAZORPAY_KEY_ID = "rzp_test_SKrPLyZWmz4GoK"
RAZORPAY_KEY_SECRET = "NAOCCEo11q48mUlneFc5x13g"