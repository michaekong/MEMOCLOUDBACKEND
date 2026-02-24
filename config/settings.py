from pathlib import Path
from datetime import timedelta
from decouple import config
import dj_database_url
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = [
   
    "memocloudbackend.onrender.com",
    "mcb.reimca-app.com",
    "frontcamsec.vercel.app",
    "127.0.0.1",
    "memocloudfront.vercel.app",
    "camsecplots.netlify.app",
    "213.199.41.196:8009"
]

# ALLOWED_HOSTS = ['*']

# Application definition
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024      # 50 Mo
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024      # 50 Mo
# Timeout upload (optionnel)
FILE_UPLOAD_TIMEOUT = 300  # secondes
INSTALLED_APPS = [
    'channels',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'users',
    'config',
    'universites',
    'memoires',
    'interactions',
    'api',
    'simple_history',
    'Documents',
    'drf_spectacular',
    'corsheaders',
   
    'django_extensions',
]

AUTH_USER_MODEL = 'users.CustomUser'

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'users.middleware.AuditMiddleware', 
]


ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # 🔑 doit contenir ton dossier templates
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

ASGI_APPLICATION = "config.asgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# DATABASES = {
#     'default': {
#         **dj_database_url.parse(config('DATABASE_URL')),
#         'ENGINE': 'django.contrib.gis.db.backends.postgis',
#         'OPTIONS': {
#             'options': '-c postgis.backend=true'
#         }
#     }
# }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

# config/settings.py
# settings.py



MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
# dossiers collectés par « collectstatic »

STATIC_URL = '/static/'  # This line must be present and correctly set
STATIC_ROOT = BASE_DIR / 'staticfiles'  # This should point to your desired directory

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
     'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_PERMISSION_CLASSES': [],
    # Optionnel : augmenter le timeout
    'DEFAULT_THROTTLE_CLASSES': [],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Configure email backend for sending verification / reset emails

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

EMAIL_HOST = config('EMAIL_HOST')
EMAIL_PORT = config('EMAIL_PORT')
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL')
EMAIL_USE_TLS = config('EMAIL_USE_TLS')


REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'MemoCloud API',
    'DESCRIPTION': 'Portail de gestion des mémoires universitaires',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,  # swagger-ui & redoc séparés
}

FRONTEND_URL = "https://memocloudfront.vercel.app"

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

CORS_ALLOWED_ORIGINS = [
    "https://memocloudbackend.onrender.com",
    "https://mcb.reimca-app.com",
    "https://memocloudfront.vercel.app",
    "https://camsecplots.netlify.app",
    "http://127.0.0.1:5500",
    "http://127.0.0.1:5501",
]


CORS_ALLOW_CREDENTIALS = True

# CORS_ALLOW_ALL_ORIGINS = True

CSRF_TRUSTED_ORIGINS = [
    "https://camsecplots.netlify.app",

    "https://frontcamsec.vercel.app",
    "https://mcb.reimca-app.com",
    "http://127.0.0.1:5500",
    "https://memocloudbackend.onrender.com",
    "http://127.0.0.1:5501",
]

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

# Redis vars
# REDIS_HOST = config("REDIS_HOST", default="127.0.0.1")
REDIS_URL = config("REDIS_URL", default="redis://redis:6379")
# REDIS_PORT = config("REDIS_PORT", default=6379, cast=int)
# REDIS_DB = config("REDIS_DB", default=0, cast=int)
# REDIS_PASSWORD = config("REDIS_PASSWORD", default=None)


# Redis pour la communication en temps réel
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],  # ou ("127.0.0.1", 6379) en local
        },
    },
}
from cryptography.fernet import Fernet

# clé 32 bytes base64 → générée une fois : Fernet.generate_key()
INVITE_CODE_KEY = b'0MYfxmqMEYbOeBXxAnC_IRA2vdYTaG7wWQ5HMy1NXD8==='