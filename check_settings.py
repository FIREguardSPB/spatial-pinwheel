import sys
sys.path.insert(0, '/home/master/Projects/Money/spatial_pinwheel/backend')
from core.storage.session import SessionLocal
from core.storage.repos import settings as settings_repo
from core.config import settings as cfg

db = SessionLocal()
try:
    s = settings_repo.get_settings(db)
    print("Settings:")
    print(f"  trade_mode: {getattr(s, 'trade_mode', None)}")
    print(f"  account_balance: {getattr(s, 'account_balance', None)}")
    print(f"  BROKER_PROVIDER from env: {cfg.BROKER_PROVIDER}")
    print(f"  LIVE_TRADING_ENABLED: {cfg.LIVE_TRADING_ENABLED}")
    print(f"  TBANK_TOKEN present: {bool(cfg.TBANK_TOKEN)}")
    print(f"  TBANK_ACCOUNT_ID present: {bool(cfg.TBANK_ACCOUNT_ID)}")
finally:
    db.close()