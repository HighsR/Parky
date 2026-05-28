import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
#not needed for docker deployment
load_dotenv(os.path.join(BASE_DIR, '.env'))
SECRET_KEY = os.environ.get('SECRET_KEY')

DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost").split(",")

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
csrf_trusted_origins_str = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if csrf_trusted_origins_str:
    CSRF_TRUSTED_ORIGINS = csrf_trusted_origins_str.split(',')

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'parking.apps.ParkingConfig',
    'channels',
    #Other apps
    "phonenumber_field",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'parky_project.urls'

DB_NAME = os.getenv('DB_NAME', 'postgres')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
DB_HOST = os.getenv('DB_HOST', 'db')
DB_PORT = os.getenv('DB_PORT', '5432')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': DB_NAME,
        'USER': DB_USER,
        'PASSWORD': DB_PASSWORD,
        'HOST': DB_HOST,
        'PORT': DB_PORT,
    }
}

LOGIN_URL='/accounts/login/'
LOGIN_REDIRECT_URL='/map/'
LOGOUT_REDIRECT_URL='/map/'

ASGI_APPLICATION = 'parky_project.asgi.application'
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(REDIS_HOST, 6379)],
        },
    },
}

LANGUAGE_CODE = 'he'

TIME_ZONE = 'Asia/Jerusalem'

PHONENUMBER_DEFAULT_REGION ='IL'

USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static',]
STATIC_ROOT = BASE_DIR / 'staticfiles'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'parking.context_processors.count_unread_notifications',
            ],
        },
    },
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
