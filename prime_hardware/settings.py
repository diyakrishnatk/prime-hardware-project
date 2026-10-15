
import os
import dj_database_url
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

# =========================================================
# 1. BASE DIRECTORY
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# =========================================================
# 2. SECURITY SETTINGS
# =========================================================


DEBUG = os.environ.get("DEBUG", "True").lower() == "true"
SECRET_KEY = os.environ.get("SECRET_KEY")

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-prime-hardware-dev-key-change-in-prod"
    else:
        raise RuntimeError(
            "SECRET_KEY environment variable is required in production."
        )

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "testserver",
    ".onrender.com",
]



# =========================================================
# 3. SESSION AND CSRF SETTINGS
# =========================================================

CSRF_USE_SESSIONS = False
SESSION_SAVE_EVERY_REQUEST = True

SESSION_COOKIE_NAME = "prime_final_session"
CSRF_COOKIE_NAME = "prime_final_csrf"

CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_HTTPONLY = True

SECURE_COOKIES = (
    os.environ.get("SECURE_COOKIES", "False").lower() == "true"
)

CSRF_COOKIE_SECURE = SECURE_COOKIES
SESSION_COOKIE_SECURE = SECURE_COOKIES

CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1",
    "http://localhost",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://0.0.0.0:8000",
    "http://0.0.0.0",
    "https://prime-hardware-project.onrender.com",
]


# =========================================================
# 4. INSTALLED APPLICATIONS
# =========================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Cloudinary image storage
    "cloudinary_storage",
    "cloudinary",

    # Main application
    "shop",
]


# =========================================================
# 5. MIDDLEWARE
# =========================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =========================================================
# 6. URL CONFIGURATION
# =========================================================

ROOT_URLCONF = "prime_hardware.urls"


# =========================================================
# 7. TEMPLATES
# =========================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "shop.context_processors.cart_renderer",
            ],
        },
    },
]


# =========================================================
# 8. WSGI APPLICATION
# =========================================================

WSGI_APPLICATION = "prime_hardware.wsgi.application"


# =========================================================
# 9. DATABASE CONFIGURATION
# =========================================================

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# =========================================================
# 10. PASSWORD VALIDATION
# =========================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# =========================================================
# 11. INTERNATIONALIZATION
# =========================================================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"

USE_I18N = True
USE_TZ = True


# =========================================================
# 12. STATIC FILES CONFIGURATION
# =========================================================

STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"


# =========================================================
# 13. CLOUDINARY CONFIGURATION
# =========================================================

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.environ.get("CLOUDINARY_CLOUD_NAME"),
    "API_KEY": os.environ.get("CLOUDINARY_API_KEY"),
    "API_SECRET": os.environ.get("CLOUDINARY_API_SECRET"),
}



# =========================================================
# 14. FILE STORAGE CONFIGURATION
# =========================================================

LOCAL_IMAGES = os.environ.get("LOCAL_IMAGES", "True").lower() == "true"

if LOCAL_IMAGES:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": (
                "whitenoise.storage.CompressedManifestStaticFilesStorage"
            ),
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": (
                "cloudinary_storage.storage.MediaCloudinaryStorage"
            ),
        },
        "staticfiles": {
            "BACKEND": (
                "whitenoise.storage.CompressedManifestStaticFilesStorage"
            ),
        },
    }

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"



# =========================================================
# 15. DEFAULT PRIMARY KEY
# =========================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# =========================================================
# 16. LOGIN AND LOGOUT
# =========================================================

LOGIN_URL = "/signin/"
LOGIN_REDIRECT_URL = "/admin-dashboard/"
LOGOUT_REDIRECT_URL = "/"



# =========================================================
# 17. EMAIL CONFIGURATION - RESEND & BREVO & SMTP
# =========================================================

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "")

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "")

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_TIMEOUT = 10
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "diyakrishnatk@gmail.com")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "qcoerfkpqicrxaop")

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL") or EMAIL_HOST_USER or RESEND_FROM_EMAIL or BREVO_SENDER_EMAIL or "diyakrishnatk@gmail.com"

# Fast2SMS Configuration (For Phone SMS OTP in India)
FAST2SMS_API_KEY = os.environ.get("FAST2SMS_API_KEY", "ZRNcDdSeKuzHFLGji6Qvl7rXx5optnUfbMBh3VCPs4a0YJOITEdHuVpn5hB4qMftXWJbE178SZFxK2TQ")




# =========================================================
# 18. RAZORPAY CONFIGURATION
# =========================================================

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
