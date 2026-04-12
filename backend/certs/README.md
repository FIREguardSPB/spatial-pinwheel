# T-Bank TLS certificates

If the worker or API fails with an SSL verification error when connecting to T-Bank, place a PEM bundle with Russian trusted roots here.

Recommended filename:

- `russian-trusted-root-ca.pem`

The adapter auto-detects these files in `backend/certs/` (or `/app/certs/` inside Docker) and appends them to the default CA bundle for both gRPC and REST requests.

You can also point to a custom bundle explicitly:

```env
TBANK_CA_CERTS_PATH=/absolute/path/to/russian-trusted-root-ca.pem
```

Expected format: PEM.
