import asyncio
import aiohttp
import sys

async def test():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get('http://localhost:8001/api/v1/ui/settings', timeout=3) as resp:
                print(f"Status: {resp.status}")
                text = await resp.text()
                print(f"Response length: {len(text)}")
                print(text[:200])
        except asyncio.TimeoutError:
            print("Timeout")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == '__main__':
    asyncio.run(test())