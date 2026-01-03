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

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-mvp-dev-key-12345')

# ⚠️ DIAGNOSIS MODE: Set to False for production!
#DEBUG = os.environ.get('DEBUG', 'False') == 'True'
DEBUG = True

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'martechjobs.io,www.martechjobs.io,martechstack.io,www.martechstack.io,.onrender.com,127.0.0.1,localhost').split(',')

CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com', 
    'https://martechjobs.io',
    'https://www.martechjobs.io',
    'https://martechstack.io',
    'https://www.martechstack.io'
]

# --- HTTPS ENFORCEMENT (SEO & SECURITY WIN) ---
if not DEBUG:
    # Redirect all HTTP traffic to HTTPS
    SECURE_SSL_REDIRECT = True
    # Tell browsers to remember to use HTTPS for 1 year (HSTS)
    SECURE_HSTS_SECONDS = 31536000 
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Ensure cookies are only sent over HTTPS
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Critical for Render/Heroku (Trusts the load balancer's SSL)
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
    
    # SEO Sitemap Support
    'django.contrib.sitemaps',
    
    # Your Apps
    'jobs',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Handles CSS/JS
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ==============================================
# DATABASE
# ==============================================
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

# 1. Static files (CSS, JS) - Managed by Whitenoise
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# 2. Media files (User Uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ==============================================
# DEFAULTS & EMAIL
# ==============================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER') 
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = f'MarTechJobs <{EMAIL_HOST_USER}>'

# STRIPE PAYMENTS
STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY", "").strip()
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()

# DOMAIN URL
DOMAIN_URL = os.environ.get("DOMAIN_URL", "https://martechjobs.io").strip()
