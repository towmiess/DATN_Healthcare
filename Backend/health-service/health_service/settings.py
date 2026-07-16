import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def load_local_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env()

MEDIA_ROOT = Path(os.getenv("HEALTH_MEDIA_ROOT", BASE_DIR / "media"))
MEDIA_URL = "/media/"
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE", str(25 * 1024 * 1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE", str(25 * 1024 * 1024)))

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "health-service-dev-secret")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")]

ENABLE_CORS = os.getenv("HEALTH_SERVICE_ENABLE_CORS", "false").lower() == "true"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "health",
]

if ENABLE_CORS:
    INSTALLED_APPS.insert(2, "corsheaders")

MIDDLEWARE = [
    "health.middleware.GatewayOnlyMiddleware",
    "django.middleware.common.CommonMiddleware",
]

if ENABLE_CORS:
    MIDDLEWARE.insert(0, "corsheaders.middleware.CorsMiddleware")

ROOT_URLCONF = "health_service.urls"
WSGI_APPLICATION = "health_service.wsgi.application"
ASGI_APPLICATION = "health_service.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "healthcare_db"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "123456"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "health.authentication.GatewayOrJwtAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = False
TIME_ZONE = "Asia/Ho_Chi_Minh"

GATEWAY_INTERNAL_SECRET = os.getenv("GATEWAY_INTERNAL_SECRET", "change-me-in-production")
JWT_ACCESS_SECRET = os.getenv("JWT_ACCESS_SECRET", "S1TZnHDnQS6ojlPYPI+bjd6CXxYhBP/eYmubZsRSANY=")
MODEL_API_URL = os.getenv("MODEL_API_URL", "")
GOOGLE_VISION_API_KEY = os.getenv("GOOGLE_VISION_API_KEY", "")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
GOOGLE_APPLICATION_CREDENTIALS_JSON = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", "")
GOOGLE_APPLICATION_CREDENTIALS_B64 = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_B64", "")


GEMINI_MODEL = os.getenv("GEMINI_MODEL", os.getenv("LLM_MODEL", "gemini-2.5-flash"))
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", os.getenv("RAG_SERVICE_URI", "http://host.docker.internal:8000"))
AI_INSIGHT_RAG_TIMEOUT = int(os.getenv("AI_INSIGHT_RAG_TIMEOUT", "12"))
AI_INSIGHT_LLM_TIMEOUT = int(os.getenv("AI_INSIGHT_LLM_TIMEOUT", "24"))
