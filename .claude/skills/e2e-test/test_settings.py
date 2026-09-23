from config.settings import *  # noqa
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "/tmp/mtj_e2e.db"}}
MIGRATION_MODULES = {"jobs": None, "accounts": None, "tools": None}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
ALLOWED_HOSTS = ["*"]
SECURE_SSL_REDIRECT = False
