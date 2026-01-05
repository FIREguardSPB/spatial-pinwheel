from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_ENV: str = "dev"
    API_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "postgresql+psycopg://bot:bot@localhost:5432/botdb"
    REDIS_URL: str = "redis://localhost:6379/0"
    SSE_KEEPALIVE_SECONDS: int = 20
    AUTH_TOKEN: str = ""
    
    # Broker Configuration
    BROKER_PROVIDER: str = "paper" # tbank, paper
    TBANK_TOKEN: str = ""
    TBANK_ACCOUNT_ID: str = ""
    
    # Feature Flags
    ALLOW_NO_REDIS: bool = False
    TBANK_SANDBOX: bool = False

settings = Settings()
