"""
Django settings for smartclub project.
Production-hardened configuration with JWT auth and RBAC.
"""
import os
from pathlib import Path
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR.parent / '.env', override=True)
except Exception:
    pass

def _env(name: str, default: str | None = None, legacy_name: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None and legacy_name:
        value = os.getenv(legacy_name)
    return default if value is None else value


def _env_bool(name: str, default: bool = False, legacy_name: str | None = None) -> bool:
    value = _env(name, None, legacy_name)
    if value is None:
        return default
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _env_list(name: str, default: str = '', legacy_name: str | None = None) -> list[str]:
    raw = _env(name, default, legacy_name) or ''
    return [item.strip() for item in raw.split(',') if item.strip()]


DEBUG = _env_bool('DJANGO_DEBUG', True, legacy_name='DEBUG')
SECRET_KEY = _env('DJANGO_SECRET_KEY', None, legacy_name='SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'dev-only-insecure-secret-key'
    else:
        raise ImproperlyConfigured('DJANGO_SECRET_KEY must be set when DJANGO_DEBUG=0.')

ALLOWED_HOSTS: list[str] = _env_list(
    'DJANGO_ALLOWED_HOSTS',
    default='localhost,127.0.0.1',
    legacy_name='ALLOWED_HOSTS',
)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    # Local apps
    'users',
    'scout',
    'physio',
    'nutri',
    'chat',
    'dashboard',
    'monitoring.apps.MonitoringConfig',
    'chat_llm',
]

AUTH_USER_MODEL = 'users.User'

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'monitoring.middleware.MetricsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'smartclub.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'smartclub.wsgi.application'

# -----------------------------------------------------------------------
# Database — SQLite locally, PostgreSQL in Docker/Production
# -----------------------------------------------------------------------
if os.getenv('USE_POSTGRES', '0') == '1':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB', 'smartclub'),
            'USER': os.getenv('POSTGRES_USER', 'smartclub'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'smartclub'),
            'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Tunis'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# -----------------------------------------------------------------------
# CORS — restrict in production via DJANGO_ALLOWED_HOSTS
# -----------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = DEBUG  # open only in dev
CORS_ALLOWED_ORIGINS = _env_list('CORS_ALLOWED_ORIGINS', 'http://localhost:3000')
CSRF_TRUSTED_ORIGINS = _env_list('CSRF_TRUSTED_ORIGINS', '')

# -----------------------------------------------------------------------
# REST Framework — JWT-first, authenticated by default
# -----------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    # Open for local dev — set env DJANGO_DEBUG=0 to enforce auth
    'DEFAULT_PERMISSION_CLASSES': [
        _env(
            'DRF_DEFAULT_PERMISSION_CLASS',
            'rest_framework.permissions.AllowAny' if DEBUG
            else 'rest_framework.permissions.IsAuthenticated',
        ),
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

if not DEBUG:
    # Production-safe defaults can still be tuned by env per deployment.
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SESSION_COOKIE_SECURE = _env_bool('SESSION_COOKIE_SECURE', True)
    CSRF_COOKIE_SECURE = _env_bool('CSRF_COOKIE_SECURE', True)
    SECURE_SSL_REDIRECT = _env_bool('SECURE_SSL_REDIRECT', False)
    SECURE_HSTS_SECONDS = int(_env('SECURE_HSTS_SECONDS', '0') or 0)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
    SECURE_HSTS_PRELOAD = _env_bool('SECURE_HSTS_PRELOAD', False)

# -----------------------------------------------------------------------
# SimpleJWT
# -----------------------------------------------------------------------
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'TOKEN_OBTAIN_SERIALIZER': 'users.serializers.SmartClubTokenObtainPairSerializer',
}

# -----------------------------------------------------------------------
# LLM / Chat AI settings
# -----------------------------------------------------------------------
LLM_PROVIDER        = os.getenv('LLM_PROVIDER', 'groq')
GROQ_API_KEY        = os.getenv('GROQ_API_KEY', '')
OPENAI_API_KEY      = os.getenv('OPENAI_API_KEY', '')
OPENROUTER_API_KEY  = os.getenv('OPENROUTER_API_KEY', '')
OLLAMA_BASE_URL     = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
LLM_MODEL           = os.getenv('LLM_MODEL', 'llama-3.1-8b-instant')
FALLBACK_PROVIDER   = os.getenv('FALLBACK_PROVIDER', '')
FALLBACK_MODEL      = os.getenv('FALLBACK_MODEL', '')

# -----------------------------------------------------------------------
# ML artifacts
# -----------------------------------------------------------------------
ML_ARTIFACTS_DIR = BASE_DIR.parent / 'ml' / 'artifacts'

# -----------------------------------------------------------------------
# SoccerMon dataset path (mounted in Docker or set via env)
# -----------------------------------------------------------------------
SOCCERMON_PATH = os.getenv(
    'SOCCERMON_PATH',
    str(BASE_DIR.parent.parent / 'smartclub_analytics' / 'subjective'),
)

# -----------------------------------------------------------------------
# FoodData Central dataset path
# -----------------------------------------------------------------------
FOODDATA_PATH = os.getenv(
    'FOODDATA_PATH',
    str(BASE_DIR.parent.parent / 'smartclub_analytics' / 'FoodData_Central_foundation_food_csv_2025-12-18'),
)