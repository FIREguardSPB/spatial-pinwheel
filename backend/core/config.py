from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "dev"
    API_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "postgresql+psycopg://bot:bot@localhost:5432/botdb"
    REDIS_URL: str = "redis://localhost:6379/0"
    SSE_KEEPALIVE_SECONDS: int = 20
    AUTH_TOKEN: str = ""

    # P8-02: Fernet key for encrypting API tokens at rest (32 url-safe base64 bytes)
    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # If empty, tokens stored in plaintext (dev mode)
    TOKEN_ENCRYPTION_KEY: str = ""

    # P1-03: CORS origins (comma-separated, replaces allow_origins=["*"])
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # P1-05: App port (single source of truth for uvicorn / docker / nginx)
    APP_PORT: int = 8000

    # Broker Configuration
    BROKER_PROVIDER: str = "paper"  # paper | tbank
    TBANK_TOKEN: str = ""
    TBANK_ACCOUNT_ID: str = ""
    LIVE_TRADING_ENABLED: bool = False
    TBANK_ORDER_TIMEOUT_SEC: float = 15.0
    TBANK_ORDER_POLL_INTERVAL_SEC: float = 0.5

    # Feature Flags
    ALLOW_NO_REDIS: bool = False
    TBANK_SANDBOX: bool = False

    OPENAI_API_KEY: str = ""
    CLAUDE_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # ── AI provider settings ──────────────────────────────────────────────────
    AI_PRIMARY_PROVIDER: str = Field(default="claude")      # claude | openai | deepseek | ollama | skip
    AI_FALLBACK_PROVIDERS: str = Field(default="deepseek,ollama,skip")
    CLAUDE_MODEL: str   = "claude-sonnet-4-6"
    OPENAI_MODEL: str   = "gpt-4o"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-reasoner"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str   = "llama3.1:8b"

    # ── InternetCollector cache TTLs (seconds) ────────────────────────────────
    NEWS_CACHE_TTL_SEC:  int = 3600    # 1 hour
    MACRO_CACHE_TTL_SEC: int = 14400   # 4 hours

    # ── Timeframe ─────────────────────────────────────────────────────────────
    TF: str = "1m"   # 1m | 5m | 15m


settings = Settings()

# ─────────────────────────────────────────────────────────────────────────────
# P8-01: Runtime token resolver
# Priority: DB (api_tokens table) > environment variable > empty string
# Usage: get_token("CLAUDE_API_KEY") instead of settings.CLAUDE_API_KEY
# ─────────────────────────────────────────────────────────────────────────────
def get_token(key_name: str, default: str = "") -> str:
    """
    Resolve a secret value with DB-first priority.
    Falls back to env-based Settings attribute or empty string.
    Designed to be called at request time (not at import time) so it always
    picks up the latest value saved via the UI.
    P8-02: Automatically decrypts Fernet-encrypted values from DB.
    """
    try:
        from core.storage.session import SessionLocal
        from core.storage.models import ApiToken
        with SessionLocal() as db:
            row = db.query(ApiToken).filter(
                ApiToken.key_name == key_name,
                ApiToken.is_active == True,   # noqa: E712
            ).first()
            if row and row.value:
                try:
                    from core.security.crypto import decrypt_token
                    return decrypt_token(row.value)
                except Exception:
                    return row.value  # fallback: return raw value
    except Exception:
        pass  # DB not ready yet (startup) — fall through to env

    # Fallback: env-based Settings attribute with matching name
    attr = getattr(settings, key_name, None)
    if attr:
        return str(attr)

    return default
