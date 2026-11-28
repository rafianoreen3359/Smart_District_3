# ---- add to settings.py -------------------------------------------------
INSTALLED_APPS += ["django_celery_beat", "automation"]

USE_TZ = True
TIME_ZONE = "Asia/Karachi"            # your local zone; crontabs are stored with it

CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# The lock needs a cache shared by all workers (not LocMemCache).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
    }
}

# Day 9 model hooks (adjust to your names)
LEDGERLINE_REPORT_MODEL = "reports.ReportRequest"   # needs: user, status, created_at, file
REPORT_FILE_FIELD = "file"
REPORT_RETENTION_DAYS = 7

# Exchange rates (free, no key): https://open.er-api.com
EXCHANGE_BASE = "USD"
EXCHANGE_SYMBOLS = ["EUR", "GBP", "PKR", "JPY", "AED", "CAD"]

LOGIN_URL = "/admin/login/"           # or your own login view

# ---- project urls.py:  path("", include("automation.urls")),
