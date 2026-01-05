# Smoke Test v1.1.0

## 1. Start Stack
Choose a profile:
```bash
# Mock Mode
docker compose --profile mock up --build -d

# OR T-Bank Sandbox (ensure .env tokens are set)
docker compose --profile tbank_sandbox up --build -d
```

## 2. API Health Check
```bash
curl http://localhost:3000/api/v1/health
```
**Expect**:
```json
{
  "status": "ok",
  "version": "v1.1.0",
  "broker": { ... }
}
```
> **Note**: If git tags are not found in the environment (e.g. shallow clone), the version is taken from `core/version.py` and `package.json`.

## 3. UI Check
1. Open `http://localhost:5173`.
2. Verify Footer shows `v1.1.0`.
3. Check Dashboard: Candles should be streaming (Mock or Real).
4. Check Connection Status (Green dot).

## 4. Signal Flow
1. Wait for Pending Signal (or trigger via script).
2. Click **Approve**.
3. Verify:
   - Notification "Signal Approved".
   - Chart shows Entry/SL/TP lines.
   - Activity Log shows `trade_filled`.
