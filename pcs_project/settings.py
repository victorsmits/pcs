"""Django settings for PCS Live — suivi de course cycliste en direct."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-pcs-live-dev-key-change-me')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost 127.0.0.1 0.0.0.0').replace(',', ' ').split()

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sites',
    # Third-party
    'django_extensions',
    'django_celery_beat',
    'django_celery_results',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    # Local apps
    'core',
    'catalog',
    'live',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

ROOT_URLCONF = 'pcs_project.urls'

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
                'core.context_processors.site_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'pcs_project.wsgi.application'

# ---------------------------------------------------------------------------
# Database — SQLite en dev, PostgreSQL si DB_HOST défini (Docker/prod)
# ---------------------------------------------------------------------------
if os.environ.get('DB_HOST'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'pcs_db'),
            'USER': os.environ.get('DB_USER', 'pcs_user'),
            'PASSWORD': os.environ.get('DB_PASSWORD', 'pcs_password'),
            'HOST': os.environ['DB_HOST'],
            'PORT': os.environ.get('DB_PORT', '5432'),
            'CONN_MAX_AGE': 60,
            'OPTIONS': {'connect_timeout': 10},
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Europe/Paris'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static / media
# ---------------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Cache — Redis si REDIS_URL défini, sinon mémoire locale (dev)
# ---------------------------------------------------------------------------
REDIS_URL = os.environ.get('REDIS_URL', '')
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'pcs-live',
        }
    }

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', REDIS_URL or 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'django-db'           # résultats visibles dans l'admin
CELERY_CACHE_BACKEND = 'django-cache'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TIMEZONE = TIME_ZONE
# En dev sans broker, exécution synchrone si CELERY_TASK_ALWAYS_EAGER=True
CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'False') == 'True'

# ---------------------------------------------------------------------------
# PCS scraping
# ---------------------------------------------------------------------------
PCS_BASE_URL = 'https://www.procyclingstats.com'
PCS_REQUEST_DELAY = float(os.environ.get('PCS_REQUEST_DELAY', '1.5'))
PCS_LIVE_POLL_INTERVAL = int(os.environ.get('PCS_LIVE_POLL_INTERVAL', '15'))  # secondes

# Circuit breaker PCS : protège PCS et nos workers en cas de blocage anti-bot persistant.
PCS_403_THRESHOLD = int(os.environ.get('PCS_403_THRESHOLD', '2'))
PCS_CIRCUIT_BACKOFFS = tuple(int(x.strip()) for x in
                             os.environ.get('PCS_CIRCUIT_BACKOFFS', '60,300,900,1800,3600').split(',')
                             if x.strip())
PCS_CIRCUIT_JITTER = float(os.environ.get('PCS_CIRCUIT_JITTER', '0.15'))
PCS_403_ALERT_AFTER_SECONDS = int(os.environ.get('PCS_403_ALERT_AFTER_SECONDS', '300'))

# ---------------------------------------------------------------------------
# Divers
# ---------------------------------------------------------------------------
ITEMS_PER_PAGE = 50
CURRENT_SEASON = int(os.environ.get('CURRENT_SEASON', '2026'))

# ---------------------------------------------------------------------------
# Authentification Google (accès admin via allauth)
# ---------------------------------------------------------------------------
LOGIN_REDIRECT_URL = '/admin/'
ACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_LOGIN_ON_GET = True          # connexion Google en 1 clic
SOCIALACCOUNT_ADAPTER = 'core.adapters.AdminSocialAdapter'
# L'email Google est vérifié → on relie/authentifie directement un compte existant
# de même email (évite l'écran de création/liaison de compte).
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
# Emails autorisés à accéder à l'admin (deviennent staff/superuser au login Google)
ADMIN_EMAILS = [e.strip().lower() for e in
                os.environ.get('ADMIN_EMAILS',
                               'victor.smits@shippingbo.com,smitsvictor97@gmail.com').split(',') if e.strip()]
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
            'secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),
            'key': '',
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    }
}

# Reverse proxy externe (TLS terminé en amont)
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = [
    'https://pcs.victorsmits.com',
    'https://www.pcs.victorsmits.com',
]

# Durcissement en production (DEBUG=False)
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 2592000          # 30 jours
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'  # callbacks OAuth en https

# --- Web Push (notifications PWA) ---
# Clé VAPID publique exposée au front, privée gardée secrète (variable d'env).
# Générer une paire : `python manage.py vapid_keys`.
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
VAPID_ADMIN_EMAIL = os.environ.get('VAPID_ADMIN_EMAIL', 'admin@pcs.victorsmits.com')
# Push actif seulement si les deux clés sont présentes (sinon dégradation propre).
PUSH_ENABLED = bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '{levelname} {asctime} {module} {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'core': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'catalog': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'live': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
    },
}
