import sys
import os
import asyncio
from pathlib import Path
from decimal import Decimal

# Add backend to sys path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# Mock settings just in case imports need it (though adapter doesn't import settings directly except types)
# actually adapter imports nothing from core.config? 
# Ah, I removed `from core.config import settings` in my adapter replacement. Good.

try:
    from apps.broker.tbank.adapter import TBankGrpcAdapter, quotation_to_decimal, decimal_to_quotation
    print("Import successful.")
except Exception as e:
    print(f"Import failed: {e}")
    sys.exit(1)

def test_decimal():
    # Test helper
    class MockQ:
        def __init__(self, u, n):
            self.units = u
            self.nano = n
    
    q = MockQ(100, 500000000)
    d = quotation_to_decimal(q)
    print(f"Decimal test: {d}")
    if d != Decimal("100.5"):
        print("Decimal conversion failed!")
        sys.exit(1)
        
    u, n = decimal_to_quotation(d)
    print(f"Reverse test: {u}, {n}")
    if u != 100 or n != 500000000:
        print("Reverse conversion failed!")
        sys.exit(1)
    print("Decimal helpers OK.")

async def test_adapter_structure():
    print("Testing adapter instantiation...")
    adapter = TBankGrpcAdapter("fake_token", "fake_account", sandbox=True)
    
    # We won't actually call network as we have no token, but we can call close
    await adapter.close()
    print("Adapter instantiated and closed.")

if __name__ == "__main__":
    test_decimal()
    asyncio.run(test_adapter_structure())
