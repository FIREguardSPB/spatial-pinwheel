import asyncio
import logging
import sys
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path

# Setup path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Mock settings before importing adapter if needed (it wasn't needed before but good practice)
# But we simply import the adapter.

from apps.broker.tbank.adapter import TBankGrpcAdapter, quotation_to_decimal, decimal_to_quotation

# Configure logging to show what's happening
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class TestTBankManual(unittest.IsolatedAsyncioTestCase):
    async def test_01_decimal_precision_strict(self):
        """Тест 1: Проверка точности Decimal (Quotation -> Decimal)."""
        logger.info("--- Тест 1: Decimal Precision ---")
        
        # Case 1: Simple
        # 114.25 => units=114, nano=250000000
        q = MagicMock()
        q.units = 114
        q.nano = 250000000
        dec = quotation_to_decimal(q)
        self.assertEqual(dec, Decimal("114.25"))
        logger.info(f"114 units + 250000000 nano => {dec} (OK)")

        # Case 2: Negative (Short)
        # -10.5 => units=-10, nano=-500000000? Or units=-10, nano=-500000000
        # T-Bank docs: both have same sign.
        q.units = -10
        q.nano = -500000000
        dec = quotation_to_decimal(q)
        self.assertEqual(dec, Decimal("-10.5"))
        logger.info(f"-10 units + -500000000 nano => {dec} (OK)")
        
        # Case 3: Strange floating point issues (0.1 + 0.2)
        # 0.3 => units=0, nano=300000000
        q.units = 0
        q.nano = 300000000
        dec = quotation_to_decimal(q)
        self.assertEqual(dec, Decimal("0.3"))
        logger.info(f"0 units + 300000000 nano => {dec} (OK)")

    async def test_02_metadata_authorization(self):
        """Тест 2: Проверка передачи токена в метаданных."""
        logger.info("--- Тест 2: Auth Metadata ---")
        adapter = TBankGrpcAdapter("test_token", "test_account")
        
        # Check metadata
        auth_header = None
        for k, v in adapter.metadata:
            if k == "authorization":
                auth_header = v
        
        self.assertEqual(auth_header, "Bearer test_token")
        logger.info(f"Metadata Authorization: {auth_header} (OK)")
        await adapter.close()

    @patch("apps.broker.tbank.adapter.marketdata_pb2_grpc.MarketDataStreamServiceStub")
    @patch("apps.broker.tbank.adapter.instruments_pb2_grpc.InstrumentsServiceStub")
    @patch("grpc.aio.secure_channel")
    async def test_03_stream_reconnect_logic(self, mock_channel, mock_instr_stub, mock_stream_stub):
        """Тест 3: Проверка реконнекта стрима при обрыве."""
        logger.info("--- Тест 3: Stream Reconnect & Backoff ---")
        
        adapter = TBankGrpcAdapter("token", "acc")
        
        # Mock Instrument Resolution (SBER -> uid_123)
        mock_instr_service = mock_instr_stub.return_value
        async def find_instrument(*args, **kwargs):
            resp = MagicMock()
            item = MagicMock()
            item.ticker = "SBER"
            item.uid = "uid_123"
            item.class_code = "TQBR"
            resp.instruments = [item]
            return resp
        mock_instr_service.FindInstrument = AsyncMock(side_effect=find_instrument)

        # Helper for Mock Quotation (concrete object, not Mock)
        class MockQ:
            def __init__(self, u, n):
                self.units = u
                self.nano = n
        
        # Custom Iterator
        class MockStream:
            def __init__(self, mode):
                self.mode = mode 
            
            def __aiter__(self):
                return self
            
            async def __anext__(self):
                if self.mode == 'error':
                    raise Exception("Simulated Connection Fail")
                elif self.mode == 'data':
                    if not hasattr(self, 'sent'):
                        self.sent = True
                        valid_candle = MagicMock()
                        valid_candle.HasField.side_effect = lambda f: f == "candle"
                        valid_candle.candle.instrument_uid = "uid_123"
                        
                        # Use concrete objects for quotations to avoid MagicMock issues with Decimal
                        c = MagicMock()
                        c.instrument_uid = "uid_123"
                        c.open = MockQ(100, 0)
                        c.high = MockQ(102, 0)
                        c.low = MockQ(99, 0)
                        c.close = MockQ(101, 500000000)
                        c.volume = 10
                        c.time = MagicMock()
                        c.time.timestamp.return_value = 1700000000.0
                        c.is_complete = False
                        
                        valid_candle.candle = c
                        return valid_candle
                    else:
                        await asyncio.sleep(0.1)
                        raise asyncio.CancelledError() 

        mock_stream_service = mock_stream_stub.return_value
        mock_stream_service.MarketDataStream.side_effect = [
            MockStream('error'),
            MockStream('data')
        ]
        
        items = []
        try:
            # Wrap in timeout to prevent infinite hanging
            async for item in adapter.stream_marketdata(["SBER"]):
                items.append(item)
                logger.info(f"Got item: close={item['close']}")
                break # We got our data, exit!
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Test runner caught exception: {e}")
            
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['instrument_id'], 'SBER')
        self.assertEqual(items[0]['broker_id'], 'uid_123')
        self.assertEqual(items[0]['close'], Decimal("101.5"))
        
        # Check call count: 1 failed + 1 success = 2 calls
        self.assertEqual(mock_stream_service.MarketDataStream.call_count, 2)
        logger.info("Reconnect logic verified: Error -> Reconnect -> Data (OK)")
        
        await adapter.close()

if __name__ == "__main__":
    unittest.main()
