import os

from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

JWT_SECRET = os.getenv("JWT_SECRET", "")
TOKEN_EXPIRY = int(os.getenv("TOKEN_EXPIRY", "60"))
STORAGE_PATH = os.getenv("STORAGE_PATH", "storage")

_origins_raw = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [origin.strip() for origin in _origins_raw.split(",") if origin.strip()]
