from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from core.config import settings

# Sync engine for MVP simplicity as requested
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    # echo=True if needed for debug
)

Base = declarative_base()
