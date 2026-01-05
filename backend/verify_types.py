import urllib.request
import json
import time

def verify():
    url = "http://localhost:8000/api/v1/candles/TQBR:SBER"
    print(f"Checking {url}...")
    
    try:
        with urllib.request.urlopen(url) as response:
            if response.status != 200:
                print(f"Error: Status {response.status}")
                return
            
            data = json.loads(response.read().decode())
            print(f"Response: {type(data)}")
            
            if isinstance(data, list) and len(data) > 0:
                candle = data[0]
                # Check types of financial fields
                close_p = candle.get("close")
                time_val = candle.get("time")
                print(f"Candle[0].close: {close_p} (Type: {type(close_p)})")
                print(f"Candle[0].time: {time_val} (Type: {type(time_val)})")
                
                if isinstance(close_p, (float, int)):
                    print("SUCCESS: 'close' is a Number.")
                else:
                    print("FAILURE: 'close' is NOT a Number.")
            else:
                print("Response is empty list (expected if Mock/Empty DB).")
                
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    max_retries = 10
    for i in range(max_retries):
        try:
            verify()
            break
        except Exception:
            if i < max_retries - 1:
                print(f"Waiting for server... ({i+1}/{max_retries})")
                time.sleep(5)
            else:
                print("Server failed to respond after retries.")
                raise
