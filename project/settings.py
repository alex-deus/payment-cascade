import logging
import os
from datetime import timedelta
from socket import gethostbyname
from uuid import uuid4

import dj_database_url
import environ
import validators
from corsheaders.defaults import default_headers
from django.utils.translation import gettext_lazy as _
from split_settings.tools import include, optional


logger = logging.getLogger("django.request")

include(optional("settings_local.py"))

root = environ.Path(__file__, "../..")

os.sys.path.insert(0, root())
os.sys.path.insert(0, os.path.join(root(), "apps"))

env = environ.Env(
    ROLE=(str, "prod"),
    DEBUG=(bool, False),
    SECRET_KEY=(str, None),
    BASE_URL=(str, None),
    BASE_FRONTEND_URL=(str, None),
    ALLOWED_HOSTS=(list, ["*"]),
    CORS_ALLOWED_ORIGINS=(list, None),
    CSRF_TRUSTED_ORIGINS=(list, None),
    #
    DB_DSN=(str, None),
    DB_USER=(str, "user"),
    DB_PASS=(str, "pass"),
    DB_HOST=(str, "pg"),
    DB_PORT=(int, 5432),
    DB_NAME=(str, "main"),
    #
    EMAIL_HOST_USER=(str, "noreply@example.com"),
    EMAIL_HOST_PASSWORD=(str, None),
    DEFAULT_FROM_EMAIL=(str, "Example <noreply@example.com>"),
    #
    REDIS_DSN=(str, "redis://redis:6379"),
    CELERY_ALWAYS_EAGER=(bool, False),
    CELERY_BROKER_URL=(str, "amqp://admin:admin@rabbit:5672/"),
    CELERY_RESULT_BACKEND=(str, "django-db"),
    #
    TAG=(str, None),
    BRANCH=(str, None),
    COMMIT=(str, None),
    #
    HOSTNAME=(str, "localhost"),
    #
    AWS_REGION=(str, "us-east-1"),
    AWS_ACCESS_KEY_ID=(str, None),
    AWS_SECRET_ACCESS_KEY=(str, None),
    AWS_S3_BUCKET_NAME=(str, "main"),
    AWS_S3_BUCKET_AUTH=(bool, True),
    AWS_S3_ENDPOINT_URL=(str, "http://s3:9000"),
    AWS_S3_PUBLIC_URL=(str, None),
    #
    SENTRY_DSN=(str, None),
    SENTRY_TRACES_SAMPLE_RATE=(float, 1.0),
    SENTRY_SEND_DEFAULT_PII=(bool, False),
    #
    AMPLITUDE_API_KEY=(str, None),
    #
    APPLE_CLIENT_ID=(str, None),
    #
    JWT_ACCESS_TOKEN_LIFETIME_MINUTES=(int, 60),
    JWT_REFRESH_TOKEN_LIFETIME_DAYS=(int, 90),
    JWT_SIGNING_KEY=(str, None),
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ROLE = env("ROLE")
DEBUG = env("DEBUG")
SECRET_KEY = env("SECRET_KEY")

TAG = env("TAG")
BRANCH = env("BRANCH")
COMMIT = env("COMMIT")

BASE_URL = env("BASE_URL")
BASE_FRONTEND_URL = env("BASE_FRONTEND_URL")

APPLE_CLIENT_ID = env("APPLE_CLIENT_ID")
APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"

ALLOWED_HOSTS = env("ALLOWED_HOSTS")
allowed_hosts = set()
for host in ALLOWED_HOSTS:
    if not validators.domain(host):
        continue

    try:
        ip: str = gethostbyname(host)
        allowed_hosts.add(ip)
    except Exception as e:
        ...

ALLOWED_HOSTS += list(allowed_hosts)
HOSTNAME = env("HOSTNAME")

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_HEADERS = ("Authorization",) + default_headers
CORS_URLS_REGEX = r"^/api/.*$"

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 Mb
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 Mb

SENTRY_DSN = env("SENTRY_DSN")
SENTRY_TRACES_SAMPLE_RATE = env("SENTRY_TRACES_SAMPLE_RATE")
SENTRY_SEND_DEFAULT_PII = env("SENTRY_SEND_DEFAULT_PII")

if SENTRY_DSN:
    from project.sentry import initialize_sentry

    initialize_sentry()

INSTALLED_APPS = [
    # admin
    "adminsortable2",
    "rangefilter",
    "jsoneditor",
    # project
    "apps.api.apps.ApiConfig",
    "apps.common.apps.CommonConfig",
    "apps.payment.apps.PaymentConfig",
    "apps.users.apps.UsersConfig",
    # django contrib
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.sitemaps",
    "django.contrib.staticfiles",
    # third-party
    "corsheaders",
    "django_celery_beat",
    "django_celery_results",
    "django_essentials_kit",
    "django_filters",
    "django_prometheus",
    "django_s3_storage",
    "djoser",
    "drf_extra_fields",
    "drf_yasg",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_extensions",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "solo",
]

MIDDLEWARE = [
    "project.middlewares.DjangoLoggingMiddleware",
    "project.middlewares.CloseOldDbConnectionsMiddleware",
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "project.middlewares.UserLocaleMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

ROOT_URLCONF = "project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [root("project/templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

WSGI_APPLICATION = "project.wsgi.application"

AUTH_USER_MODEL = "users.User"

DB_DSN = env("DB_DSN")
if DB_DSN:
    DATABASES = {"default": dj_database_url.config(default=env("DB_DSN"))}
    DATABASES["default"].update({"TEST": {"NAME": f"test_{uuid4().hex[:6]}"}})
    DATABASES["default"]["CONN_MAX_AGE"] = 300
    DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
    DATABASES["default"]["OPTIONS"] = {
        "connect_timeout": 5,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    }

else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME"),
            "USER": env("DB_USER"),
            "PASSWORD": env("DB_PASS"),
            "HOST": env("DB_HOST"),
            "PORT": env("DB_PORT"),
            "CONN_MAX_AGE": 300,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "connect_timeout": 5,
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 3,
            },
        }
    }

FIXTURE_DIRS = [root("project/fixtures")]
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

REDIS_DSN = env("REDIS_DSN")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

USE_TZ = True
TIME_ZONE = "Europe/Moscow"

LANGUAGE_CODE = "en"
LANGUAGES = [("en", _("English")), ("ru", "Русский")]
USE_I18N = True
USE_L10N = True
LOCALE_PATHS = [root("project/locale")]

MEDIA_URL = "/media/"
MEDIA_ROOT = root("media")

STATIC_URL = "/static/"
STATIC_ROOT = root("static")
STATICFILES_DIRS = [root("project/static")]

STORAGES = {
    "default": {"BACKEND": "django_s3_storage.storage.S3Storage"},
    "media": {"BACKEND": "django_s3_storage.storage.S3Storage"},
    "staticfiles": {"BACKEND": "django_s3_storage.storage.S3Storage"},
}

AWS_REGION = env("AWS_REGION")
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
AWS_S3_BUCKET_NAME = env("AWS_S3_BUCKET_NAME")
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL")
AWS_S3_PUBLIC_URL = env("AWS_S3_PUBLIC_URL")
AWS_S3_BUCKET_AUTH = env("AWS_S3_BUCKET_AUTH")
AWS_S3_MAX_AGE_SECONDS = 60 * 60 * 24 * 2
AWS_S3_CONTENT_DISPOSITION = lambda n: f'attachment; filename="{n.split("/")[-1]}"'
AWS_S3_FILE_OVERWRITE = True

REST_FRAMEWORK_EXTENSIONS = {
    "DEFAULT_CACHE_RESPONSE_TIMEOUT": 60 * 15,
    "DEFAULT_USE_CACHE": "api",
}
REST_FRAMEWORK = {
    "PAGE_SIZE": 100,
    "UPLOADED_FILES_USE_URL": env("ROLE") != "test",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env("JWT_ACCESS_TOKEN_LIFETIME_MINUTES")),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env("JWT_REFRESH_TOKEN_LIFETIME_DAYS")),
    "SIGNING_KEY": env("JWT_SIGNING_KEY") or SECRET_KEY,
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,  # лишний UPDATE на каждый refresh
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}
SWAGGER_SETTINGS = {
    "SECURITY_DEFINITIONS": {
        "Token": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Enter 'Token {value}' (without quotes) to access this API.",
        },
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Enter 'Bearer {access_token}' (without quotes) to access this API.",
        },
    },
    "SECURITY": [{"Token": []}, {"Bearer": []}],
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "root": {"level": "INFO", "handlers": ["console"]},
    "formatters": {
        "verbose": {
            "()": "project.logger_formatter.JSONFormatter",
            "format": "[%(levelname)s][%(asctime)s] %(module)s.%(funcName)s:%(lineno)d: %(message)s",
        },
    },
    "handlers": {
        "console": {"level": "INFO", "class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "loggers": {
        "celery": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "celery.tasks": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "django": {"level": "DEBUG", "handlers": ["console"], "propagate": False},
        "django.server": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "django.request": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "django.commands": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "django.db.backends": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "httpx": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "requests": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "urllib3": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "google_genai": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

APPEND_SLASH = True

LOGIN_URL = "/admin/login/"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"{REDIS_DSN}/2",
        "TIMEOUT": 300,
        "KEY_PREFIX": "django_cache",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 1,
            "SOCKET_TIMEOUT": 2,
            "RETRY_ON_TIMEOUT": True,
            "IGNORE_EXCEPTIONS": True,
        },
    },
    "api": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"{REDIS_DSN}/3",
        "KEY_PREFIX": "api",
        "TIMEOUT": 300,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 1,
            "SOCKET_TIMEOUT": 2,
            "RETRY_ON_TIMEOUT": True,
            "IGNORE_EXCEPTIONS": True,
        },
    },
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND")
CELERY_ENABLE_UTC = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERYD_TIME_LIMIT = 200
CELERYD_SOFT_TIME_LIMIT = 120
CELERY_TASK_TRACK_STARTED = True
CELERY_ALWAYS_EAGER = env("CELERY_ALWAYS_EAGER")
CELERY_TASK_EAGER_PROPAGATES = env("CELERY_ALWAYS_EAGER")

PROMETHEUS_LATENCY_BUCKETS = (
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    2.5,
    5.0,
    7.5,
    10.0,
    25.0,
    50.0,
    75.0,
    float("inf"),
)

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")

IMAGEKIT_CACHEFILE_NAMER = "imagekit.cachefiles.namers.hash"
IMAGEKIT_DEFAULT_CACHEFILE_STRATEGY = "imagekit.cachefiles.strategies.JustInTime"

AMPLITUDE_API_KEY = env("AMPLITUDE_API_KEY")

IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"

if ROLE == "test":
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

    class DisableMigrations(object):
        def __contains__(self, item):
            return True

        def __getitem__(self, item):
            return None

    MIGRATION_MODULES = DisableMigrations()

    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

    CELERY_ALWAYS_EAGER = True

    SECURE_PROXY_SSL_HEADER = ()
    del LOGGING["formatters"]["verbose"]["()"]

    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.filesystem.FileSystemStorage"},
        "media": {"BACKEND": "django.core.files.storage.filesystem.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.core.files.storage.filesystem.FileSystemStorage"},
    }

elif ROLE == "debug":
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

    SECURE_PROXY_SSL_HEADER = ()
    del LOGGING["formatters"]["verbose"]["()"]

elif ROLE == "dev":
    ...

elif ROLE == "staging":
    ...

elif ROLE == "prod":
    ...

import django
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy


django.utils.translation.ugettext = gettext_lazy
django.utils.encoding.force_text = force_str

from django.conf.locale.en import formats as en_formats


en_formats.DATETIME_FORMAT = "Y-m-d H:i:s"

include(optional("settings_local.py"))
