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
    'jazzmin',
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
    # 'accounts' MUST come before allauth so our custom templates in
    # accounts/templates/account/ override allauth's defaults (the app
    # template loader resolves in INSTALLED_APPS order, first match wins).
    'accounts',
    # --- ALLAUTH ---
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    # ---------------
    'jobs',
    'tools',
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
                'accounts.context_processors.feature_flags',
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
# Low-friction signups: don't gate accounts behind email verification. We send
# our own branded welcome email on signup instead (accounts/signals.py).
ACCOUNT_EMAIL_VERIFICATION = 'none'
LOGIN_REDIRECT_URL = '/accounts/dashboard/'
LOGOUT_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_ON_GET = False
ACCOUNT_ADAPTER = 'accounts.adapter.AccountAdapter'

# ==============================================
# GOOGLE OAUTH (django-allauth socialaccount)
# Activates automatically when the two env vars are set on Render — no code
# change needed. Get them from Google Cloud Console → Credentials → OAuth
# client (Web application). Authorized redirect URI:
#   https://martechjobs.io/accounts/google/login/callback/
# ==============================================
GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID', '').strip()
GOOGLE_OAUTH_SECRET = os.environ.get('GOOGLE_OAUTH_SECRET', '').strip()
GOOGLE_OAUTH_ENABLED = bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_SECRET)

# Go straight to Google on click (skip allauth's intermediate confirm page).
SOCIALACCOUNT_LOGIN_ON_GET = True
# Google has already verified the email, so don't re-verify.
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_EMAIL_REQUIRED = True
# Auto-link a Google login to an existing local account with the same email
# (handled in accounts/adapter.py:SocialAccountAdapter.pre_social_login) so
# email-first users can sign in with Google without hitting a signup screen.
SOCIALACCOUNT_ADAPTER = 'accounts.adapter.SocialAccountAdapter'
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    }
}
if GOOGLE_OAUTH_ENABLED:
    SOCIALACCOUNT_PROVIDERS['google']['APPS'] = [{
        'client_id': GOOGLE_OAUTH_CLIENT_ID,
        'secret': GOOGLE_OAUTH_SECRET,
        'key': '',
    }]

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

# ==============================================
# JAZZMIN — Admin UI Theme
# ==============================================
JAZZMIN_SETTINGS = {
    "site_title": "MarTechJobs Admin",
    "site_header": "MarTechJobs",
    "site_brand": "MarTechJobs",
    "welcome_sign": "Welcome to MarTechJobs Admin",
    "copyright": "MarTechJobs.io",
    "search_model": ["jobs.Job", "jobs.ActiveJob", "auth.User"],
    "topmenu_links": [
        {"name": "🏠 Founder HQ", "url": "/staff/"},
        {"name": "🧐 Review Queue", "url": "/staff/review/"},
        {"model": "jobs.ActiveJob"},
        {"name": "View Site", "url": "/", "new_window": True},
    ],
    "usermenu_links": [
        {"name": "Founder HQ", "url": "/staff/"},
        {"name": "View Site", "url": "/", "new_window": True},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    # Sidebar quick links — the "sections" of the admin, website-style.
    "custom_links": {
        "jobs": [
            {"name": "🏠 Founder HQ", "url": "/staff/", "icon": "fas fa-home"},
            {"name": "🧐 Review Queue", "url": "/staff/review/", "icon": "fas fa-clipboard-check"},
            {"name": "📊 Public Stats Page", "url": "/martech-job-market-statistics/", "icon": "fas fa-chart-bar", "new_window": True},
        ],
    },
    # People first (the founder's #1 question is "who are my users"), then the
    # job pipeline, then content, then system config.
    "order_with_respect_to": [
        "auth.User",
        "accounts.ProWaitlistEntry",
        "jobs.Subscriber",
        "jobs.SavedSearch",
        "jobs.ActiveJob",
        "jobs.Job",
        "jobs.UserSubmission",
        "jobs.CompanySource",
        "jobs.BlogPost",
        "jobs.InterviewGuide",
        "jobs.CertificationGuide",
        "jobs.Tool",
        "jobs.Category",
        "jobs.BlockRule",
        "auth",
    ],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "accounts.ProWaitlistEntry": "fas fa-gem",
        "jobs.ActiveJob": "fas fa-briefcase",
        "jobs.Job": "fas fa-hourglass-half",
        "jobs.UserSubmission": "fas fa-inbox",
        "jobs.CompanySource": "fas fa-database",
        "jobs.BlogPost": "fas fa-pen-nib",
        "jobs.InterviewGuide": "fas fa-comments",
        "jobs.CertificationGuide": "fas fa-certificate",
        "jobs.Tool": "fas fa-tools",
        "jobs.Category": "fas fa-tags",
        "jobs.Subscriber": "fas fa-envelope",
        "jobs.SavedSearch": "fas fa-search",
        "jobs.BlockRule": "fas fa-ban",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": True,
    "custom_css": None,
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "auth.user": "collapsible",
        "auth.group": "vertical_tabs",
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-dark",
    "accent": "accent-primary",
    "navbar": "navbar-dark",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}
