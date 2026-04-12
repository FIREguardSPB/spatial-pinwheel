import sys
sys.path.insert(0, '/home/master/Projects/Money/spatial_pinwheel/backend')
from core.config import settings as cfg
from core.storage.session import SessionLocal
from core.storage.repos import settings as settings_repo

def _live_broker_runtime_enabled(s):
    trade_mode = str(getattr(s, "trade_mode", "review") or "review")
    return (
        cfg.BROKER_PROVIDER == "tbank"
        and trade_mode == "auto_live"
        and bool(cfg.TBANK_TOKEN)
        and bool(cfg.TBANK_ACCOUNT_ID)
        and bool(cfg.LIVE_TRADING_ENABLED)
    )

db = SessionLocal()
try:
    s = settings_repo.get_settings(db)
    print(f"BROKER_PROVIDER: {cfg.BROKER_PROVIDER}")
    print(f"trade_mode: {getattr(s, 'trade_mode', None)}")
    print(f"TBANK_TOKEN: {bool(cfg.TBANK_TOKEN)}")
    print(f"TBANK_ACCOUNT_ID: {bool(cfg.TBANK_ACCOUNT_ID)}")
    print(f"LIVE_TRADING_ENABLED: {cfg.LIVE_TRADING_ENABLED}")
    print(f"Result: {_live_broker_runtime_enabled(s)}")
finally:
    db.close()