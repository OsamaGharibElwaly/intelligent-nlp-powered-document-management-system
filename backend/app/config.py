import os

from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_HTTP_CONNECT_TIMEOUT = float(os.getenv("GROQ_HTTP_CONNECT_TIMEOUT", "10"))
GROQ_HTTP_READ_TIMEOUT = float(os.getenv("GROQ_HTTP_READ_TIMEOUT", "55"))
GROQ_MAX_ATTEMPTS = max(1, int(os.getenv("GROQ_MAX_ATTEMPTS", "3")))
GROQ_RETRY_BACKOFF_MS = max(50, int(os.getenv("GROQ_RETRY_BACKOFF_MS", "400")))

JWT_SECRET = os.getenv("JWT_SECRET", "")
TOKEN_EXPIRY = int(os.getenv("TOKEN_EXPIRY", "60"))
STORAGE_PATH = os.getenv("STORAGE_PATH", "storage")

# Dev bootstrap: POST /admin/bootstrap/promote (never expose this value to clients).
ADMIN_BOOTSTRAP_SECRET = os.getenv("ADMIN_BOOTSTRAP_SECRET", "").strip()

_origins_raw = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [origin.strip() for origin in _origins_raw.split(",") if origin.strip()]
