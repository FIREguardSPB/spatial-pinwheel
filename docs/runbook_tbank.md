# T-Bank Integration Runbook

## 1. Overview
Direct gRPC integration with T-Bank Invest API (v2).
- **Protocol**: gRPC (Protobuf)
- **Library**: `grpcio`, `protobuf` (official Google libs)
- **Adapter**: `backend/apps/broker/tbank/adapter.py`

## 2. Configuration
Environment variables (.env):

```bash
# Broker Provider
BROKER_PROVIDER=tbank

# Auth (Required for T-Bank)
TBANK_TOKEN=<your_token>
TBANK_ACCOUNT_ID=<your_account_id>

# Feature Flags
ALLOW_NO_REDIS=false # Set to true only for local dev without Redis
```

## 3. Sandbox Mode
To use T-Bank Sandbox:
1. Generate a Sandbox Token at [developers.tbank.ru](https://developers.tbank.ru/).
2. Set in `.env`:
   ```bash
   TBANK_TOKEN=<sandbox_token>
   ```
3. **Switch to Sandbox Mode**:
   Sandbox is controlled via environment variable (no code changes required).
   
   *In `.env`*:
   ```bash
   TBANK_SANDBOX=true   # Default: false
   ```
   
   The adapter will automatically select the Sandbox endpoint when this flag is enabled.

## 4. Verification Commands

### Check Stream (Manual Script)
Run the dedicated verification script to test connection, auth, and data streaming:

```bash
cd backend
python verify_tbank_grpc.py
```
*Expected Output:*
```
Health Check: True
Resolved TQBR:SBER -> <uid>
Stream started...
Candle: time=..., close=...
```

### Check Worker Logs
When running the full stack:
```bash
# In backend/
uvicorn apps.api.main:app --reload
python apps/worker/main.py
```
*Look for:*
`Connected to T-Bank stream for X instruments.`

## 5. Troubleshooting

### "Stream error: StatusCode.UNAUTHENTICATED"
- **Cause**: Invalid Token or Sandbox Token used for Prod (or vice-versa).
- **Fix**: Check `TBANK_TOKEN` and ensure you are hitting the correct endpoint.

### "Redis publish failed"
- **Cause**: Redis is down.
- **Fix**: Start Redis OR set `ALLOW_NO_REDIS=true` in `.env` (Dev only).

### "ModuleNotFoundError: No module named 'investapi.gen'"
- **Cause**: Protobufs not generated.
- **Fix**: Run generation script:
  ```bash
  python backend/gen_protos.py
  ```
