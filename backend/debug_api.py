import asyncio
import httpx


async def debug_api():
    base_url = "http://localhost:3000/api/v1"

    print(f"Checking API at {base_url}...")

    # 1. Create a Signal to store in DB
    # We need to manually insert into DB or use an endpoint if available.
    # The worker logic creates signals, but we can try to use the 'signals' repo via code if API doesn't allow creation.
    # Actually, let's just check the /candles endpoint or /signals if there are any.
    # If DB is empty, we might not see anything.

    # Let's try to fetch signals.
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{base_url}/signals")
            print(f"GET /signals Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"Response Type: {type(data)}")
                if isinstance(data, list) and len(data) > 0:
                    sig = data[0]
                    entry = sig.get("entry")
                    print(f"Signal[0].entry value: {entry!r}")
                    print(f"Signal[0].entry type: {type(entry)}")
                else:
                    print(
                        "No signals found. Creating one via direct DB insertion (simulated) or just checking candles..."
                    )
        except Exception as e:
            print(f"Error fetching signals: {e}")

        # 2. Check Candles (Mock or TBank)
        # If we are mock, candles are empty list currently in API?
        # Wait, the API candles endpoint was modified to use TBank adapter.
        # If TBank is configured, it calls adapter.
        # If not, it returns [].

        try:
            resp = await client.get(f"{base_url}/candles/TQBR:SBER")
            print(f"GET /candles Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    candle = data[0]
                    close_p = candle.get("close")
                    print(f"Candle[0].close value: {close_p!r}")
                    print(f"Candle[0].close type: {type(close_p)}")
                else:
                    print("No candles returned.")
        except Exception as e:
            print(f"Error fetching candles: {e}")


if __name__ == "__main__":
    asyncio.run(debug_api())
