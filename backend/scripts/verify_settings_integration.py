import requests
import json
import sys

BASE_URL = "http://localhost:3000/api/v1"

def run_verification():
    print(f"Checking API at {BASE_URL}...")
    
    # 1. GET Settings
    try:
        resp = requests.get(f"{BASE_URL}/settings")
    except Exception as e:
        print(f"FAIL: Could not connect to API: {e}")
        return False
        
    if resp.status_code != 200:
        print(f"FAIL: GET /settings returned {resp.status_code}")
        print(resp.text)
        return False
        
    data = resp.json()
    print("GET /settings OK")
    
    # 2. Check Fields
    required_fields = [
        "risk_profile", 
        "atr_stop_hard_min", "atr_stop_hard_max", "decision_threshold",
        "w_regime", "w_volatility", "w_momentum", "w_levels", "w_costs", "w_liquidity"
    ]
    
    missing = [f for f in required_fields if f not in data]
    if missing:
        print(f"FAIL: Missing fields in response: {missing}")
        return False
        
    print(f"Field Check OK using data: {json.dumps(data, indent=2)}")
    
    # 3. PUT Update
    print("\nTesting Update...")
    original_val = data.get("w_regime", 20)
    new_val = 25 if original_val != 25 else 20
    
    payload = data.copy()
    payload["w_regime"] = new_val
    
    resp_put = requests.put(f"{BASE_URL}/settings", json=payload)
    if resp_put.status_code != 200:
        print(f"FAIL: PUT /settings returned {resp_put.status_code}")
        print(resp_put.text)
        return False
        
    updated_data = resp_put.json()
    if updated_data["w_regime"] != new_val:
        print(f"FAIL: PUT did not update value. Expected {new_val}, got {updated_data['w_regime']}")
        return False
        
    print(f"PUT Update OK. w_regime changed from {original_val} to {new_val}")
    
    # 4. Verify Persistence (GET again)
    resp_get2 = requests.get(f"{BASE_URL}/settings")
    data2 = resp_get2.json()
    if data2["w_regime"] != new_val:
        print(f"FAIL: Persistence check failed. Got {data2['w_regime']}")
        return False
        
    print("Persistence Check OK")
    
    # 5. Revert
    payload["w_regime"] = original_val
    requests.put(f"{BASE_URL}/settings", json=payload)
    print("Reverted changes.")
    
    return True

if __name__ == "__main__":
    success = run_verification()
    if not success:
        sys.exit(1)
