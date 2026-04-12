import sys
sys.path.insert(0, '/home/master/Projects/Money/spatial_pinwheel/backend')
from core.storage.session import SessionLocal
from core.storage.models import ApiToken

db = SessionLocal()
try:
    tokens = db.query(ApiToken).all()
    for t in tokens:
        print(f"{t.name}: {t.value[:20]}... (active={t.active})")
finally:
    db.close()