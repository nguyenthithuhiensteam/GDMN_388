"""
Cấu hình Django cho hệ thống quản trị trường mầm non.

Mọi thông tin bí mật (SECRET_KEY, mật khẩu CSDL, email, khóa AI) được đọc từ
biến môi trường hoặc tệp .env (không đưa vào Git). Xem .env.example.

DJANGO_ENV: development | testing | production
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

try:  # Tải tệp .env nếu có (chỉ tiện cho máy phát triển / máy chủ đơn)
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:  # pragma: no cover
    pass


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DJANGO_ENV = env("DJANGO_ENV", "development")
IS_PRODUCTION = DJANGO_ENV == "production"

DEBUG = env_bool("DJANGO_DEBUG", not IS_PRODUCTION)

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise ImproperlyConfigured("Thiếu biến môi trường DJANGO_SECRET_KEY.")
    # Khóa chỉ dùng cho máy phát triển; không bao giờ dùng ở môi trường chính thức.
    SECRET_KEY = "dev-only-insecure-key-do-not-use-in-production"

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "apps.accounts",
    "apps.org",
    "apps.core",
    "apps.content",
    "apps.office",
    "apps.reports",
    "apps.ai_assistant",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.accounts.middleware.ActiveSessionMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Cơ sở dữ liệu -----------------------------------------------------------
# Phát triển: SQLite. Chính thức: PostgreSQL qua DB_ENGINE=postgresql.
if env("DB_ENGINE", "sqlite") == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "mamnon"),
            "USER": env("DB_USER", "mamnon"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(env("DB_CONN_MAX_AGE", "60")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

# Giới hạn đăng nhập sai
LOGIN_MAX_FAILURES = int(env("LOGIN_MAX_FAILURES", "5"))
LOGIN_LOCKOUT_MINUTES = int(env("LOGIN_LOCKOUT_MINUTES", "15"))

# --- Ngôn ngữ, múi giờ ----------------------------------------------------------
LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True
DATE_FORMAT = "d/m/Y"
DATETIME_FORMAT = "d/m/Y H:i"
SHORT_DATE_FORMAT = "d/m/Y"
SHORT_DATETIME_FORMAT = "d/m/Y H:i"
DATE_INPUT_FORMATS = ["%d/%m/%Y", "%Y-%m-%d"]
DATETIME_INPUT_FORMATS = ["%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
USE_THOUSAND_SEPARATOR = False

# --- Tệp tĩnh & tệp tải lên --------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = Path(env("STATIC_ROOT", str(BASE_DIR / "staticfiles")))
STATICFILES_DIRS = [BASE_DIR / "static"]

# Tệp công khai (ảnh bài viết, logo, album đã duyệt): được web server phục vụ trực tiếp.
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))
# Tệp nội bộ (văn bản, minh chứng, kế hoạch...): KHÔNG phục vụ trực tiếp,
# chỉ tải qua view có kiểm tra quyền.
PROTECTED_MEDIA_ROOT = Path(env("PROTECTED_MEDIA_ROOT", str(BASE_DIR / "protected_media")))
# Nếu dùng Nginx: đặt "/_protected/" để dùng X-Accel-Redirect (xem deploy/nginx.conf)
PROTECTED_MEDIA_ACCEL_PREFIX = env("PROTECTED_MEDIA_ACCEL_PREFIX", "")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
            if IS_PRODUCTION
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}

MAX_UPLOAD_MB = int(env("MAX_UPLOAD_MB", "20"))
MAX_IMAGE_MB = int(env("MAX_IMAGE_MB", "8"))
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_PERMISSIONS = 0o640
IMAGE_MAX_DIMENSION = int(env("IMAGE_MAX_DIMENSION", "1920"))

BACKUP_DIR = Path(env("BACKUP_DIR", str(BASE_DIR / "backups")))
BACKUP_KEEP = int(env("BACKUP_KEEP", "14"))

TRUST_X_REAL_IP = env_bool("TRUST_X_REAL_IP", False)

# --- Email -------------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@localhost")
EMAIL_NOTIFICATIONS_ENABLED = env_bool("EMAIL_NOTIFICATIONS_ENABLED", False)

# --- Phiên đăng nhập & bảo mật ---------------------------------------------------
SESSION_COOKIE_AGE = int(env("SESSION_COOKIE_AGE", str(8 * 3600)))
SESSION_EXPIRE_AT_BROWSER_CLOSE = env_bool("SESSION_EXPIRE_AT_BROWSER_CLOSE", True)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

if IS_PRODUCTION:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
    SECURE_HSTS_PRELOAD = False

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "mamnon",
    }
}

# --- AI hỗ trợ (tùy chọn) ------------------------------------------------------
AI_ENABLED = env_bool("AI_ENABLED", False)
AI_API_KEY = env("ANTHROPIC_API_KEY", "")
AI_MODEL = env("AI_MODEL", "claude-opus-5-5")
# Mặc định KHÔNG gửi nội dung tài liệu nội bộ ra dịch vụ bên ngoài.
AI_ALLOW_INTERNAL_DOCUMENTS = env_bool("AI_ALLOW_INTERNAL_DOCUMENTS", False)
AI_MAX_INPUT_CHARS = int(env("AI_MAX_INPUT_CHARS", "20000"))
AI_EFFORT = env("AI_EFFORT", "medium")

# --- Nhật ký -----------------------------------------------------------------
LOG_DIR = Path(env("LOG_DIR", str(BASE_DIR / "logs")))
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
if IS_PRODUCTION and env_bool("LOG_TO_FILE", True):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOGGING["handlers"]["file"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "filename": str(LOG_DIR / "app.log"),
        "maxBytes": 10 * 1024 * 1024,
        "backupCount": 5,
        "formatter": "simple",
    }
    LOGGING["root"]["handlers"].append("file")
    LOGGING["loggers"]["django.security"]["handlers"].append("file")

ADMINS = [("Admin", e) for e in env_list("DJANGO_ADMIN_EMAILS")]

if DJANGO_ENV == "testing":
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

import sys  # noqa: E402

if "test" in sys.argv:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    MEDIA_ROOT = BASE_DIR / ".test_media"
    PROTECTED_MEDIA_ROOT = BASE_DIR / ".test_protected_media"
    BACKUP_DIR = BASE_DIR / ".test_backups"
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
