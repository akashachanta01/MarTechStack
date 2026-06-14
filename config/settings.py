"""
Django settings for config project.
"""
import dj_database_url
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================
# SECURITY & PRODUCTION CONFIG
# ==============================================

# SECURITY WARNING: don't run with debug turned on in production!
# We now check the Environment Variable. If not set, it defaults to False.
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# SECURITY WARNING: keep the secret key used in production secret!
# In production the SECRET_KEY env var is required; the insecure fallback
# is only allowed while DEBUG=True (local development).
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-debug-key-123'
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured("SECRET_KEY environment variable is required in production.")

# Only accept requests addressed to our real domains (prevents Host-header attacks).
ALLOWED_HOSTS = [
    'martechjobs.io', 'www.martechjobs.io',
    'martechstack.io', 'www.martechstack.io',
    '.onrender.com',
]
if DEBUG:
    ALLOWED_HOSTS += ['localhost', '127.0.0.1']

CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com', 
    'https://martechjobs.io',
    'https://www.martechjobs.io',
    'https://martechstack.io',
    'https://www.martechstack.io'
]

# --- HTTPS ENFORCEMENT ---
# We disable HTTPS enforcement while Debugging to prevent redirect loops on some platforms
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000 
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ==============================================
# APPLICATION DEFINITION
# ==============================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # --- REQUIRED FOR SEO SITEMAPS ---
    'django.contrib.sites',
    'django.contrib.sitemaps',
    # ---------------------------------
    'django.contrib.humanize',
    # --- ALLAUTH ---
    'allauth',
    'allauth.account',
    # ---------------
    'jobs',
    'tools',
    'accounts',
]

# Required for django.contrib.sites
SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Redirect old domain to new domain
    'jobs.middleware.DomainRedirectMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [], 
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'jobs.context_processors.global_seo_data',
                'jobs.context_processors.seo_indexing',
                'accounts.context_processors.saved_job_ids',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ==============================================
# DATABASE
# ==============================================
# Uses DATABASE_URL from Render if available, otherwise falls back to SQLite
DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///' + str(BASE_DIR / 'db.sqlite3'),
        conn_max_age=600
    )
}

# ==============================================
# PASSWORDS
# ==============================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==============================================
# INTERNATIONALIZATION
# ==============================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ==============================================
# STATIC & MEDIA FILES
# ==============================================
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ==============================================
# DEFAULTS & EMAIL
# ==============================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# SMTP server is env-driven so we can switch providers (Gmail -> Resend) by
# changing Render env vars only, no code deploy. Defaults keep Gmail working.
#   Resend:  EMAIL_HOST=smtp.resend.com  EMAIL_PORT=587  EMAIL_HOST_USER=resend
#            EMAIL_HOST_PASSWORD=<resend api key>  DEFAULT_FROM_EMAIL="MarTechJobs <alerts@martechjobs.io>"
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com').strip()
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'true').strip().lower() == 'true'

# SAFE DEFAULTS: Prevents 500 error if these variables are missing
# EMAIL_HOST_USER is the SMTP *username* (Gmail: the address; Resend: "resend").
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'martechjobs@gmail.com').strip()
# Gmail App Passwords are 16 chars and NEVER contain spaces — Google only
# *displays* them in groups of four. Strip any spaces so a copy-paste with the
# display formatting (e.g. "evov hyih ilex xcox") still authenticates correctly.
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '').replace(' ', '').strip()
# The visible "From" address. With Resend this must be on a verified domain.
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', f'MarTechJobs <{EMAIL_HOST_USER}>').strip()
# A real, monitored inbox for replies and admin notifications. Kept separate
# from EMAIL_HOST_USER because the SMTP username may not be a real address.
CONTACT_EMAIL = os.environ.get('CONTACT_EMAIL', 'martechjobs@gmail.com').strip()

STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY", "").strip()
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()

# Strip trailing slashes to prevent url errors
DOMAIN_URL = os.environ.get("DOMAIN_URL", "https://martechjobs.io").strip().rstrip('/')

# ==============================================
# AUTHENTICATION BACKENDS
# ==============================================
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# ==============================================
# DJANGO-ALLAUTH
# ==============================================
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
LOGIN_REDIRECT_URL = '/accounts/dashboard/'
LOGOUT_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_ON_GET = False
ACCOUNT_ADAPTER = 'accounts.adapter.AccountAdapter'

# ==============================================
# CACHE
# On multi-worker Render the default per-process LocMemCache makes cache
# invalidation and rate-limiting incorrect across workers. Use a shared Redis
# cache when REDIS_URL is set (Django 4.2 has a built-in backend — no extra
# dependency); otherwise fall back to LocMemCache so local/dev still works.
# ==============================================
REDIS_URL = os.environ.get('REDIS_URL', '').strip()
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
        }
    }

# ==============================================
# LOGGING — ensure app errors (e.g. email/SMTP failures) reach Render logs
# ==============================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "loggers": {
        "jobs": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
}
