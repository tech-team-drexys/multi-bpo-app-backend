from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-erp-multibpo-dev-key-change-in-production-2025')

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_celery_beat',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
]

LOCAL_APPS = [
    'apps.authentication.apps.AuthenticationConfig',
    'apps.dashboard.apps.DashboardConfig',
    'apps.documents.apps.DocumentsConfig',
    'apps.clients.apps.ClientsConfig',
    'apps.chat.apps.ChatConfig',
    'apps.utilities.apps.UtilitiesConfig',
    'apps.noticias.apps.NoticiasConfig',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ===== CONFIGURAÇÃO DE AUTENTICAÇÃO =====

# Modelo de usuário customizado
AUTH_USER_MODEL = 'authentication.User'

# Backend de autenticação
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

# ===== MIDDLEWARE =====

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'erp_multibpo.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',  # Templates globais
            BASE_DIR / 'apps' / 'authentication' / 'templates',  # Templates de email
        ],
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

WSGI_APPLICATION = 'erp_multibpo.wsgi.application'

# ===== DATABASE =====

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'erp_multibpo_db'),
        'USER': os.getenv('DB_USER', 'erp_multibpo_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'erp_multibpo_2025_secure'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5433'),
    }
}

# ===== REST FRAMEWORK CONFIGURATION =====

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',  # Para Django Admin
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
    # Configurações de throttling para API
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'luca_anon': '4/week',      # 4 perguntas por semana para anônimos
        'luca_user': '11/week',     # 11 perguntas por semana para cadastrados
    }
}

# ===== JWT CONFIGURATION =====

from datetime import timedelta

SIMPLE_JWT = {
    # Configurações de tempo de vida dos tokens
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),       # Token expira em 1 hora
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),       # Refresh expira em 7 dias
    'ROTATE_REFRESH_TOKENS': True,                     # Gera novo refresh a cada uso
    'BLACKLIST_AFTER_ROTATION': True,                  # Adiciona token antigo à blacklist
    
    # Configurações de assinatura
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': 'multibpo-erp',
    
    # Headers JWT
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    
    # Claims customizados
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_CLAIM': 'jti',
    
    # Configurações de sliding tokens (não usado, mas disponível)
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

# ===== PASSWORD VALIDATION =====

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ===== INTERNATIONALIZATION =====

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# ===== STATIC FILES =====

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# ===== MEDIA FILES =====

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ===== DEFAULT PRIMARY KEY =====

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ===== LOGGING CONFIGURATION =====

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.authentication': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}



# ===== SESSION CONFIGURATION =====

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400  # 1 dia
SESSION_COOKIE_NAME = 'erp_multibpo_sessionid'
SESSION_COOKIE_SECURE = False  # True em produção
SESSION_COOKIE_HTTPONLY = True

# ===== SECURITY SETTINGS =====

# CORS configuração será no development.py/production.py
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# ===== CLOUDFLARE TURNSTILE (Placeholder) =====

TURNSTILE_SECRET_KEY = os.getenv('TURNSTILE_SECRET_KEY', '')
TURNSTILE_SITE_KEY = os.getenv('TURNSTILE_SITE_KEY', '')

# ===== SOCIAL LOGIN CONFIGURATION =====

# Google OAuth
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')

# Facebook OAuth
FACEBOOK_APP_ID = os.getenv('FACEBOOK_APP_ID', '')
FACEBOOK_APP_SECRET = os.getenv('FACEBOOK_APP_SECRET', '')

# ===== N8N INTEGRATION =====

N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', '')
N8N_API_KEY = os.getenv('N8N_API_KEY', '')

# ===== CUSTOM SETTINGS MULTI BPO =====

# Limites de perguntas Luca IA
LUCA_ANONYMOUS_LIMIT = 4
LUCA_REGISTERED_LIMIT = 11
LUCA_RESET_DAYS = 7

# URLs do sistema
FRONTEND_URL = 'http://localhost:3000'  # Será sobrescrito em development/production
SITE_URL = 'https://multibpo.com.br'

# Email settings serão definidos em development/production