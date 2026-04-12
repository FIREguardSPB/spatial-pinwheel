from __future__ import annotations

import sys
import os
import asyncio
import time
import logging
import importlib
import tempfile
import re
from pathlib import Path
from decimal import Decimal, ROUND_FLOOR
from typing import AsyncGenerator, Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from collections import deque

import httpx

from core.utils.http_client import make_async_client

from core.config import settings
from apps.broker.tbank.adapter_support import interval_to_rest as _interval_to_rest, normalize_instrument_id, parse_api_timestamp as _parse_api_timestamp

try:
    import certifi
except Exception:  # pragma: no cover - optional dependency
    certifi = None  # type: ignore[assignment]

try:
    import grpc
    _GRPC_RUNTIME_IMPORT_ERROR: Optional[Exception] = None
except Exception as exc:  # pragma: no cover - depends on runtime environment
    grpc = None  # type: ignore[assignment]
    _GRPC_RUNTIME_IMPORT_ERROR = exc

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
GEN_DIR = BASE_DIR / "vendor" / "investapi" / "gen"
_GOOGLE_GEN_DIR = GEN_DIR / "google"

try:
    from google.protobuf.timestamp_pb2 import Timestamp
    _TIMESTAMP_IMPORT_ERROR: Optional[Exception] = None
except Exception as exc:  # pragma: no cover - depends on runtime environment
    Timestamp = None  # type: ignore[assignment]
    _TIMESTAMP_IMPORT_ERROR = exc

# Add backend/vendor/investapi/gen to sys.path only after importing google.protobuf.
# The generated grpc bundle contains vendor/investapi/gen/google/__init__.py, which can
# shadow the real site-packages namespace package `google` and break `google.protobuf`.
if str(GEN_DIR) not in sys.path:
    sys.path.append(str(GEN_DIR))

# If google namespace package is already imported from site-packages, expose generated
# google.api modules to it without letting vendor stubs shadow google.protobuf.
if _GOOGLE_GEN_DIR.exists() and 'google' in sys.modules:
    google_pkg = sys.modules['google']
    google_path = getattr(google_pkg, '__path__', None)
    if google_path is not None and str(_GOOGLE_GEN_DIR) not in google_path:
        google_path.append(str(_GOOGLE_GEN_DIR))

common_pb2 = None
marketdata_pb2 = None
marketdata_pb2_grpc = None
instruments_pb2 = None
instruments_pb2_grpc = None
users_pb2 = None
users_pb2_grpc = None
_GRPC_IMPORT_ERROR: Optional[Exception] = None

_NANO = Decimal("1000000000")
PROD_ENDPOINT = "invest-public-api.tbank.ru:443"
SANDBOX_ENDPOINT = "sandbox-invest-public-api.tbank.ru:443"
REST_API_PREFIX = "https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1"

_TRADING_STATUS_ALLOWED = {
    "SECURITY_TRADING_STATUS_NORMAL_TRADING",
    "SECURITY_TRADING_STATUS_SESSION_OPEN",
    "SECURITY_TRADING_STATUS_OPENING_PERIOD",
    "SECURITY_TRADING_STATUS_OPENING_AUCTION_PERIOD",
    "SECURITY_TRADING_STATUS_DEALER_NORMAL_TRADING",
    "SECURITY_TRADING_STATUS_TRADING_AT_CLOSING_AUCTION_PRICE",
}
_ORDER_STATUS_TERMINAL = {
    "EXECUTION_REPORT_STATUS_FILL",
    "EXECUTION_REPORT_STATUS_REJECTED",
    "EXECUTION_REPORT_STATUS_CANCELLED",
}


_REQUIRED_STUB_MODULES = (
    "common_pb2",
    "marketdata_pb2",
    "marketdata_pb2_grpc",
    "instruments_pb2",
    "instruments_pb2_grpc",
    "users_pb2",
    "users_pb2_grpc",
)


def _generated_stubs_ready() -> bool:
    return all((GEN_DIR / f"{module}.py").exists() for module in _REQUIRED_STUB_MODULES)


def _sanitize_generated_google_package() -> None:
    conflict_init = _GOOGLE_GEN_DIR / "__init__.py"
    if conflict_init.exists():
        try:
            conflict_init.unlink()
            logger.warning("Removed conflicting generated google package stub at %s", conflict_init)
        except OSError as exc:
            logger.warning("Could not remove conflicting google package stub %s: %s", conflict_init, exc)

    if _GOOGLE_GEN_DIR.exists() and 'google' in sys.modules:
        google_pkg = sys.modules['google']
        google_path = getattr(google_pkg, '__path__', None)
        if google_path is not None and str(_GOOGLE_GEN_DIR) not in google_path:
            google_path.append(str(_GOOGLE_GEN_DIR))


def _ensure_generated_stubs() -> None:
    _sanitize_generated_google_package()
    if _generated_stubs_ready():
        return

    proto_dir = BASE_DIR / "vendor" / "investapi" / "proto"
    if not proto_dir.exists():
        raise RuntimeError(
            f"T-Bank proto sources were not found in {proto_dir}; cannot generate gRPC stubs"
        )

    try:
        from gen_protos import generate_grpc
    except Exception as exc:  # pragma: no cover - import depends on runtime env
        raise RuntimeError(
            "Unable to import gen_protos.generate_grpc(); install backend dependencies first"
        ) from exc

    logger.warning("Generated T-Bank gRPC stubs were missing; regenerating them in %s", GEN_DIR)
    generate_grpc()


def _load_grpc_modules() -> None:
    global common_pb2, marketdata_pb2, marketdata_pb2_grpc
    global instruments_pb2, instruments_pb2_grpc, users_pb2, users_pb2_grpc, _GRPC_IMPORT_ERROR

    if all(
        module is not None
        for module in (
            common_pb2,
            marketdata_pb2,
            marketdata_pb2_grpc,
            instruments_pb2,
            instruments_pb2_grpc,
            users_pb2,
            users_pb2_grpc,
        )
    ):
        return

    if _TIMESTAMP_IMPORT_ERROR is not None or Timestamp is None:
        raise RuntimeError(
            "google.protobuf is unavailable; install backend dependencies with `pip install -e .[dev]`"
        ) from _TIMESTAMP_IMPORT_ERROR

    try:
        _ensure_generated_stubs()
        _sanitize_generated_google_package()
        common_pb2 = importlib.import_module("common_pb2")
        marketdata_pb2 = importlib.import_module("marketdata_pb2")
        marketdata_pb2_grpc = importlib.import_module("marketdata_pb2_grpc")
        instruments_pb2 = importlib.import_module("instruments_pb2")
        instruments_pb2_grpc = importlib.import_module("instruments_pb2_grpc")
        users_pb2 = importlib.import_module("users_pb2")
        users_pb2_grpc = importlib.import_module("users_pb2_grpc")
        _GRPC_IMPORT_ERROR = None
    except Exception as exc:
        _GRPC_IMPORT_ERROR = exc
        raise RuntimeError(
            "Failed to load T-Bank gRPC stubs. Ensure backend/vendor/investapi/gen contains generated *_pb2 files or run `python gen_protos.py`."
        ) from exc


class TBankApiError(RuntimeError):
    pass


class TBankOrderRejected(TBankApiError):
    pass


def quotation_to_decimal(q) -> Decimal:
    if not q:
        return Decimal("0")
    return Decimal(q.units) + (Decimal(q.nano) / _NANO)


def decimal_to_quotation(x: Decimal):
    units = int(x)
    nano = int((x - Decimal(units)) * _NANO)
    return units, nano


def _new_timestamp() -> Timestamp:
    if Timestamp is None:
        raise RuntimeError(
            "google.protobuf Timestamp is unavailable; install backend dependencies with `pip install -e .[dev]`"
        ) from _TIMESTAMP_IMPORT_ERROR
    return Timestamp()


def now_timestamp() -> Timestamp:
    ts = _new_timestamp()
    ts.GetCurrentTime()
    return ts


def dt_to_timestamp(dt: datetime) -> Timestamp:
    ts = _new_timestamp()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts.FromDatetime(dt)
    return ts


def money_to_decimal(value: Optional[dict[str, Any]]) -> Decimal:
    if not value:
        return Decimal("0")
    units = Decimal(str(value.get("units", 0) or 0))
    nano = Decimal(str(value.get("nano", 0) or 0)) / _NANO
    return units + nano


def decimal_to_money_value(amount: Decimal, currency: str = "RUB") -> dict[str, Any]:
    normalized = amount.quantize(Decimal("0.01"))
    units = int(normalized.to_integral_value(rounding=ROUND_FLOOR))
    nano = int((normalized - Decimal(units)) * _NANO)
    return {
        "currency": currency.upper(),
        "units": str(units),
        "nano": nano,
    }


def quotation_dict_to_decimal(value: Optional[dict[str, Any]]) -> Decimal:
    if not value:
        return Decimal("0")
    units = Decimal(str(value.get("units", 0) or 0))
    nano = Decimal(str(value.get("nano", 0) or 0)) / _NANO
    return units + nano


def _raw_setting(name: str, default: Any = None) -> Any:
    env_value = os.getenv(name)
    if env_value not in (None, ""):
        return env_value
    try:
        value = getattr(settings, name)
    except Exception:
        value = default
    return default if value in (None, "") else value


def _string_setting(name: str, default: Optional[str] = None) -> Optional[str]:
    value = _raw_setting(name, default)
    if value in (None, ""):
        return default
    return str(value)


def _bool_setting(name: str, default: bool) -> bool:
    value = _raw_setting(name, None)
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _existing_file(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    p = Path(path).expanduser()
    if p.is_file():
        return str(p)
    if not p.is_absolute():
        candidate = (BASE_DIR / p).resolve()
        if candidate.is_file():
            return str(candidate)
    return None


def _discover_extra_ca_bundle() -> Optional[str]:
    candidates = [
        _string_setting("TBANK_CA_CERTS_PATH"),
        _string_setting("TBANK_EXTRA_CA_CERTS_PATH"),
        str(BASE_DIR / "certs" / "tbank-root-ca.pem"),
        str(BASE_DIR / "certs" / "russian-trusted-root-ca.pem"),
        str(BASE_DIR / "certs" / "russian-trusted-ca.pem"),
        str(BASE_DIR / "certs" / "mincifry-root-ca.pem"),
    ]
    for candidate in candidates:
        resolved = _existing_file(candidate)
        if resolved:
            return resolved
    return None


def _default_base_ca_bundle() -> Optional[str]:
    for candidate in (
        _string_setting("SSL_CERT_FILE"),
        _string_setting("REQUESTS_CA_BUNDLE"),
        certifi.where() if certifi is not None else None,
        "/etc/ssl/certs/ca-certificates.crt",
        "/etc/pki/tls/certs/ca-bundle.crt",
        "/etc/ssl/cert.pem",
    ):
        resolved = _existing_file(candidate)
        if resolved:
            return resolved
    return None


def _write_temp_bundle(prefix: str, data: bytes) -> str:
    tmp = tempfile.NamedTemporaryFile(prefix=prefix, suffix=".pem", delete=False)
    tmp.write(data)
    tmp.flush()
    tmp.close()
    return tmp.name


def _split_pem_certificates(data: bytes) -> list[bytes]:
    matches = re.findall(
        rb"-----BEGIN CERTIFICATE-----\s+.*?-----END CERTIFICATE-----\s*",
        data,
        flags=re.DOTALL,
    )
    return [m.strip() + b"\n" for m in matches]


def _merge_ca_bundles(base_bundle_path: Optional[str], extra_bundle_path: Optional[str]) -> tuple[Optional[bytes], Optional[str]]:
    if not extra_bundle_path:
        return None, base_bundle_path

    chunks: list[bytes] = []
    for path in (base_bundle_path, extra_bundle_path):
        if not path:
            continue
        with open(path, "rb") as fh:
            data = fh.read().strip()
        if data:
            chunks.append(data + b"\n")

    if not chunks:
        return None, None

    merged_bytes = b"".join(chunks)
    return merged_bytes, _write_temp_bundle("tbank-ca-", merged_bytes)


def _build_grpc_tls_variants(
    *,
    base_bundle_path: Optional[str],
    extra_bundle_path: Optional[str],
    merged_bytes: Optional[bytes],
    merged_path: Optional[str],
) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    seen: set[tuple[Optional[bytes], Optional[str]]] = set()

    def add_variant(label: str, root_certificates: Optional[bytes], env_roots_path: Optional[str]) -> None:
        key = (root_certificates, env_roots_path)
        if key in seen:
            return
        seen.add(key)
        variants.append(
            {
                "label": label,
                "root_certificates": root_certificates,
                "env_roots_path": env_roots_path,
            }
        )

    if merged_bytes:
        add_variant("merged-bytes", merged_bytes, None)

    extra_bytes: Optional[bytes] = None
    root_only_bytes: Optional[bytes] = None
    root_only_path: Optional[str] = None
    if extra_bundle_path:
        with open(extra_bundle_path, "rb") as fh:
            extra_bytes = fh.read().strip() or None
        if extra_bytes:
            extra_bytes = extra_bytes + b"\n"
            add_variant("extra-bundle-bytes", extra_bytes, None)
            certs = _split_pem_certificates(extra_bytes)
            if certs:
                # For gRPC/BoringSSL the trust store is often more reliable when it
                # contains only trust anchors (root CA), not the full chain with
                # intermediates. We assume the last certificate in the user-provided
                # bundle is the root CA, which matches the bundle we ask users to build.
                root_only_bytes = certs[-1]
                root_only_path = _write_temp_bundle("tbank-root-only-", root_only_bytes)
                add_variant("root-only-bytes", root_only_bytes, None)

    if merged_path:
        add_variant("grpc-default-roots=merged-file", None, merged_path)
    if root_only_path:
        add_variant("grpc-default-roots=root-only-file", None, root_only_path)
    if extra_bundle_path:
        add_variant("grpc-default-roots=extra-file", None, extra_bundle_path)
    if base_bundle_path:
        add_variant("grpc-default-roots=system-file", None, base_bundle_path)
    add_variant("grpc-builtin-defaults", None, None)
    return variants


class TBankGrpcAdapter:
    def __init__(self, token: str, account_id: str, sandbox: bool = False):
        self.token = token
        self.account_id = account_id
        self.sandbox = sandbox
        self.target = SANDBOX_ENDPOINT if sandbox else PROD_ENDPOINT
        self.credentials = None
        self.metadata = (
            ("authorization", f"Bearer {token}"),
            ("x-app-name", "team.botpanel"),
        )
        self._channel = None
        self._figi_cache: Dict[str, str] = {}
        self._instrument_cache: Dict[str, dict[str, Any]] = {}
        self._instrument_missing_cache: Dict[str, float] = {}
        self._instrument_missing_ttl_sec = max(60.0, float(_string_setting("TBANK_MISSING_INSTRUMENT_TTL_SEC", "600") or "600"))
        # T-Bank REST docs use the same invest-public-api.tbank.ru host for both live and sandbox,
        # but the path must use dotted service notation:
        #   .../tinkoff.public.invest.api.contract.v1.InstrumentsService/FindInstrument
        self._rest_api_prefix = _string_setting("TBANK_REST_BASE_URL")
        if sandbox:
            self._rest_api_prefix = self._rest_api_prefix or _string_setting("TBANK_SANDBOX_REST_BASE_URL")
        self._rest_api_prefix = (self._rest_api_prefix or REST_API_PREFIX).rstrip("/")
        self._base_ca_bundle_path = _default_base_ca_bundle()
        self._extra_ca_bundle_path = _discover_extra_ca_bundle()
        self._stream_mode = (_string_setting("TBANK_STREAM_MODE", "rest_poll" if sandbox else "auto") or ("rest_poll" if sandbox else "auto")).strip().lower()
        self._stream_poll_interval_sec = max(2.0, float(_string_setting("TBANK_STREAM_POLL_INTERVAL_SEC", "5") or "5"))
        configured_extra_bundle = _string_setting("TBANK_CA_CERTS_PATH")
        if configured_extra_bundle and not self._extra_ca_bundle_path:
            raise TBankApiError(
                f"TBANK_CA_CERTS_PATH points to a missing file: {configured_extra_bundle}"
            )
        self._grpc_root_certificates, self._http_verify = _merge_ca_bundles(
            self._base_ca_bundle_path, self._extra_ca_bundle_path
        )
        self._grpc_tls_variants = _build_grpc_tls_variants(
            base_bundle_path=self._base_ca_bundle_path,
            extra_bundle_path=self._extra_ca_bundle_path,
            merged_bytes=self._grpc_root_certificates,
            merged_path=self._http_verify,
        )
        self._grpc_tls_variant_index = 0
        self._grpc_tls_variant_label = self._grpc_tls_variants[0]["label"] if self._grpc_tls_variants else "grpc-builtin-defaults"
        self._grpc_target_name_override = _string_setting("TBANK_GRPC_SSL_TARGET_NAME")
        self._ssl_verify_enabled = _bool_setting("TBANK_SSL_VERIFY", True)
        if self._extra_ca_bundle_path:
            logger.info("Using additional T-Bank CA bundle from %s", self._extra_ca_bundle_path)
        if not self._ssl_verify_enabled:
            logger.warning("REST TLS verification is disabled via TBANK_SSL_VERIFY=false")
        self._stats_started_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        self._request_stats: dict[str, Any] = {
            "started_ts": self._stats_started_ts,
            "requests_total": 0,
            "success_total": 0,
            "error_total": 0,
            "requests_by_method": {},
            "success_by_method": {},
            "error_by_method": {},
            "last_error": None,
            "last_rate_limit_remaining": None,
            "last_rate_limit_reset": None,
        }
        self._recent_requests: deque[float] = deque(maxlen=2048)

    def _record_rest_stat(self, method: str, *, ok: bool, status_code: int | None = None, rate_limit_remaining: str | None = None, rate_limit_reset: str | None = None, detail: str | None = None) -> None:
        stats = self._request_stats
        stats["requests_total"] = int(stats.get("requests_total", 0)) + 1
        bucket = stats.setdefault("requests_by_method", {})
        bucket[method] = int(bucket.get(method, 0)) + 1
        self._recent_requests.append(time.monotonic())
        if ok:
            stats["success_total"] = int(stats.get("success_total", 0)) + 1
            sb = stats.setdefault("success_by_method", {})
            sb[method] = int(sb.get(method, 0)) + 1
        else:
            stats["error_total"] = int(stats.get("error_total", 0)) + 1
            eb = stats.setdefault("error_by_method", {})
            eb[method] = int(eb.get(method, 0)) + 1
            stats["last_error"] = {
                "method": method,
                "status_code": status_code,
                "detail": detail,
                "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            }
        if rate_limit_remaining is not None:
            stats["last_rate_limit_remaining"] = rate_limit_remaining
        if rate_limit_reset is not None:
            stats["last_rate_limit_reset"] = rate_limit_reset

    def get_runtime_stats(self) -> dict[str, Any]:
        stats = dict(self._request_stats)
        now = time.monotonic()
        while self._recent_requests and now - self._recent_requests[0] > 60.0:
            self._recent_requests.popleft()
        recent_count = len(self._recent_requests)
        rps = recent_count / 60.0 if recent_count else 0.0
        recommendation = "ok"
        if rps >= 20:
            recommendation = "Высокая нагрузка: увеличьте poll interval или уменьшите watchlist"
        elif rps >= 10:
            recommendation = "Средняя нагрузка: следите за лимитами и unresolved instruments"
        stats.update({
            "recent_requests_60s": recent_count,
            "requests_per_sec": round(rps, 2),
            "recommendation": recommendation,
        })
        return stats

    def _current_grpc_tls_variant(self) -> dict[str, Any]:
        if not self._grpc_tls_variants:
            return {"label": "grpc-builtin-defaults", "root_certificates": None, "env_roots_path": None}
        return self._grpc_tls_variants[self._grpc_tls_variant_index]

    def _apply_grpc_roots_env(self, path: Optional[str]) -> None:
        if path:
            os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = path
        else:
            os.environ.pop("GRPC_DEFAULT_SSL_ROOTS_FILE_PATH", None)

    @staticmethod
    def _is_grpc_ssl_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(
            marker in message
            for marker in (
                "certificate verify failed",
                "self-signed certificate",
                "tls",
                "ssl",
                "handshake failed",
            )
        )

    async def _advance_grpc_tls_variant(self, exc: Exception) -> bool:
        if not self._is_grpc_ssl_error(exc):
            return False
        if self._grpc_tls_variant_index + 1 >= len(self._grpc_tls_variants):
            return False

        failed_label = self._current_grpc_tls_variant().get("label", "unknown")
        self._grpc_tls_variant_index += 1
        next_label = self._current_grpc_tls_variant().get("label", "unknown")
        await self.close()
        logger.warning(
            "gRPC TLS verification failed using %s; retrying with %s",
            failed_label,
            next_label,
        )
        return True

    async def _get_channel(self):
        if grpc is None:
            raise TBankApiError(
                "grpcio is unavailable; install backend dependencies with `pip install -e .[dev]`"
            ) from _GRPC_RUNTIME_IMPORT_ERROR
        if self._channel is None:
            variant = self._current_grpc_tls_variant()
            self._grpc_tls_variant_label = variant.get("label", "grpc-builtin-defaults")
            self._apply_grpc_roots_env(variant.get("env_roots_path"))
            if self.credentials is None:
                self.credentials = grpc.ssl_channel_credentials(
                    root_certificates=variant.get("root_certificates")
                )
            options: list[tuple[str, str]] = [("grpc.primary_user_agent", "team.botpanel")]
            if self._grpc_target_name_override:
                options.extend(
                    [
                        ("grpc.ssl_target_name_override", self._grpc_target_name_override),
                        ("grpc.default_authority", self._grpc_target_name_override),
                    ]
                )
            self._channel = grpc.aio.secure_channel(self.target, self.credentials, options=options)
        return self._channel

    async def close(self):
        if self._channel:
            await self._channel.close()
            self._channel = None
        self.credentials = None

    async def _rest_post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-app-name": "team.botpanel",
        }
        url = f"{self._rest_api_prefix}.{method}"
        client_kwargs: dict[str, Any] = {"timeout": httpx.Timeout(connect=10.0, read=20.0, write=20.0, pool=10.0), "limits": httpx.Limits(max_connections=100, max_keepalive_connections=20)}
        if not self._ssl_verify_enabled:
            client_kwargs["verify"] = False
        elif self._http_verify:
            client_kwargs["verify"] = self._http_verify
        async with make_async_client(**client_kwargs) as client:
            resp = await client.post(url, json=payload, headers=headers)
        rate_limit_remaining = resp.headers.get("x-ratelimit-remaining") or resp.headers.get("rate_limit_remaining")
        rate_limit_reset = resp.headers.get("x-ratelimit-reset") or resp.headers.get("rate_limit_reset")
        if resp.status_code >= 400:
            detail = resp.text
            try:
                data = resp.json()
                detail = data.get("message") or data.get("description") or detail
            except Exception:
                pass
            self._record_rest_stat(method, ok=False, status_code=resp.status_code, rate_limit_remaining=rate_limit_remaining, rate_limit_reset=rate_limit_reset, detail=detail)
            raise TBankApiError(f"{method} failed with HTTP {resp.status_code}: {detail}")
        data = resp.json()
        if isinstance(data, dict) and data.get("code") and data.get("message"):
            detail = f"{data.get('message')} ({data.get('code')})"
            self._record_rest_stat(method, ok=False, status_code=resp.status_code, rate_limit_remaining=rate_limit_remaining, rate_limit_reset=rate_limit_reset, detail=detail)
            raise TBankApiError(f"{method} failed: {detail}")
        self._record_rest_stat(method, ok=True, status_code=resp.status_code, rate_limit_remaining=rate_limit_remaining, rate_limit_reset=rate_limit_reset)
        return data

    async def health_check(self) -> bool:
        try:
            await self.resolve_account_id(self.account_id or None)
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def _account_list_method(self) -> str:
        return "SandboxService/GetSandboxAccounts" if self.sandbox else "UsersService/GetAccounts"

    def _portfolio_method(self) -> str:
        return "SandboxService/GetSandboxPortfolio" if self.sandbox else "OperationsService/GetPortfolio"

    def _positions_method(self) -> str:
        return "SandboxService/GetSandboxPositions" if self.sandbox else "OperationsService/GetPositions"

    def _withdraw_limits_method(self) -> str:
        return "SandboxService/GetSandboxWithdrawLimits" if self.sandbox else "OperationsService/GetWithdrawLimits"

    def _post_order_method(self) -> str:
        return "SandboxService/PostSandboxOrder" if self.sandbox else "OrdersService/PostOrder"

    def _order_state_method(self) -> str:
        return "SandboxService/GetSandboxOrderState" if self.sandbox else "OrdersService/GetOrderState"

    async def get_accounts(self) -> list[dict[str, Any]]:
        data = await self._rest_post(self._account_list_method(), {"status": "ACCOUNT_STATUS_ALL"})
        return data.get("accounts", []) or []

    async def get_bank_accounts(self) -> list[dict[str, Any]]:
        if self.sandbox:
            return []
        data = await self._rest_post("UsersService/GetBankAccounts", {})
        return data.get("bankAccounts") or data.get("accounts") or []

    async def open_sandbox_account(self, name: Optional[str] = None) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if name:
            payload["name"] = name
        return await self._rest_post("SandboxService/OpenSandboxAccount", payload)

    async def sandbox_pay_in(self, *, account_id: str, amount: Decimal, currency: str = "RUB") -> dict[str, Any]:
        return await self._rest_post(
            "SandboxService/SandboxPayIn",
            {
                "accountId": account_id,
                "amount": decimal_to_money_value(amount, currency),
            },
        )

    async def pay_in(self, *, from_account_id: str, to_account_id: str, amount: Decimal, currency: str = "RUB") -> dict[str, Any]:
        if self.sandbox:
            raise TBankApiError("UsersService/PayIn is not available for sandbox mode")
        return await self._rest_post(
            "UsersService/PayIn",
            {
                "fromAccountId": from_account_id,
                "toAccountId": to_account_id,
                "amount": decimal_to_money_value(amount, currency),
            },
        )

    async def currency_transfer(self, *, from_account_id: str, to_account_id: str, amount: Decimal, currency: str = "RUB") -> dict[str, Any]:
        if self.sandbox:
            raise TBankApiError("UsersService/CurrencyTransfer is not available for sandbox mode")
        return await self._rest_post(
            "UsersService/CurrencyTransfer",
            {
                "fromAccountId": from_account_id,
                "toAccountId": to_account_id,
                "amount": decimal_to_money_value(amount, currency),
            },
        )

    async def resolve_account_id(self, preferred_account_id: Optional[str] = None) -> str:
        accounts = await self.get_accounts()
        if not accounts:
            if self.sandbox:
                raise TBankApiError("No sandbox accounts available for the provided T-Bank token")
            raise TBankApiError("No brokerage accounts available for the provided T-Bank token")

        def _account_id(acc: dict[str, Any]) -> str:
            return str(acc.get("id") or acc.get("accountId") or acc.get("brokerAccountId") or "")

        def _is_usable(acc: dict[str, Any]) -> bool:
            status = acc.get("status")
            if self.sandbox:
                return status in {"ACCOUNT_STATUS_OPEN", "ACCOUNT_STATUS_NEW"}
            return (
                status == "ACCOUNT_STATUS_OPEN"
                and acc.get("accessLevel") == "ACCOUNT_ACCESS_LEVEL_FULL_ACCESS"
            )

        if preferred_account_id:
            for account in accounts:
                if _account_id(account) == preferred_account_id:
                    if not _is_usable(account):
                        raise TBankApiError(
                            f"T-Bank account {preferred_account_id} is not available for {'sandbox' if self.sandbox else 'live'} trading"
                        )
                    self.account_id = preferred_account_id
                    return preferred_account_id
            raise TBankApiError(f"Configured TBANK_ACCOUNT_ID {preferred_account_id} was not found")

        usable_accounts = [acc for acc in accounts if _is_usable(acc)]
        if len(usable_accounts) == 1:
            self.account_id = _account_id(usable_accounts[0])
            return self.account_id
        if not usable_accounts:
            if self.sandbox:
                raise TBankApiError("No OPEN sandbox T-Bank accounts available for sandbox trading")
            raise TBankApiError("No OPEN/FULL_ACCESS T-Bank accounts available for live trading")
        raise TBankApiError(
            f"Multiple {'sandbox' if self.sandbox else 'live'} T-Bank accounts available; specify TBANK_ACCOUNT_ID explicitly"
        )

    async def search_instruments(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        found = await self._rest_post(
            "InstrumentsService/FindInstrument",
            {"query": query, "apiTradeAvailableFlag": True},
        )
        items = []
        for item in (found.get("instruments", []) or [])[:limit]:
            class_code = (item.get("classCode") or "TQBR").upper()
            ticker = (item.get("ticker") or "").upper()
            instrument_id = normalize_instrument_id(f"{class_code}:{ticker}" if ticker else (item.get("uid") or item.get("figi") or query))
            items.append({
                "instrument_id": instrument_id,
                "ticker": ticker or instrument_id.split(":")[-1],
                "name": item.get("name") or ticker or instrument_id,
                "exchange": class_code,
                "currency": item.get("currency") or "RUB",
                "type": item.get("instrumentType") or "stock",
                "lot": int(item.get("lot") or 1),
                "price_step": 0,
                "is_tradable": bool(item.get("apiTradeAvailableFlag", True)),
                "uid": item.get("uid"),
                "figi": item.get("figi"),
            })
        return items

    async def resolve_instrument(self, instrument_id: str) -> Optional[str]:
        details = await self.get_instrument_details(instrument_id)
        return details.get("uid") if details else None

    async def get_instrument_details(self, instrument_id: str) -> dict[str, Any]:
        instrument_id = normalize_instrument_id(instrument_id)
        if instrument_id in self._instrument_cache:
            return self._instrument_cache[instrument_id]

        missing_until = self._instrument_missing_cache.get(instrument_id)
        if missing_until and missing_until > asyncio.get_running_loop().time():
            raise TBankApiError(f"Instrument temporarily marked unavailable: {instrument_id}")
        self._instrument_missing_cache.pop(instrument_id, None)

        if len(instrument_id) == 36 and "-" in instrument_id:
            query_value = instrument_id
        else:
            query_value = instrument_id.split(":")[-1]
        class_code = instrument_id.split(":")[0] if ":" in instrument_id else None

        found = await self._rest_post(
            "InstrumentsService/FindInstrument",
            {"query": query_value, "apiTradeAvailableFlag": True},
        )
        candidates = found.get("instruments", []) or []
        selected: Optional[dict[str, Any]] = None
        for item in candidates:
            if class_code and item.get("classCode") and item.get("classCode") != class_code:
                continue
            if item.get("ticker") == query_value or item.get("uid") == query_value or item.get("figi") == query_value:
                selected = item
                break
        if selected is None and candidates:
            selected = candidates[0]
        if selected is None:
            self._instrument_missing_cache[instrument_id] = asyncio.get_running_loop().time() + self._instrument_missing_ttl_sec
            raise TBankApiError(f"Instrument not found via T-Bank API: {instrument_id}")

        instrument = await self._rest_post(
            "InstrumentsService/GetInstrumentBy",
            {"idType": "INSTRUMENT_ID_TYPE_UID", "id": selected.get("uid")},
        )
        payload = instrument.get("instrument") or {}
        details = {
            "uid": payload.get("uid") or selected.get("uid"),
            "figi": payload.get("figi") or selected.get("figi"),
            "ticker": payload.get("ticker") or selected.get("ticker"),
            "class_code": payload.get("classCode") or selected.get("classCode"),
            "name": payload.get("name") or selected.get("name"),
            "lot": int(payload.get("lot") or 1),
            "currency": payload.get("currency") or "RUB",
            "buy_available": bool(payload.get("buyAvailableFlag", True)),
            "sell_available": bool(payload.get("sellAvailableFlag", True)),
            "api_trade_available": bool(payload.get("apiTradeAvailableFlag", True)),
            "short_enabled": bool(payload.get("shortEnabledFlag", False)),
            "trading_status": payload.get("tradingStatus") or "SECURITY_TRADING_STATUS_UNSPECIFIED",
            "instrument_type": payload.get("instrumentType") or selected.get("instrumentType"),
            "min_price_increment": quotation_dict_to_decimal(payload.get("minPriceIncrement")),
        }
        self._instrument_cache[instrument_id] = details
        self._instrument_missing_cache.pop(instrument_id, None)
        if details.get("uid"):
            self._figi_cache[instrument_id] = details["uid"]
        return details

    async def ensure_instrument_tradable(self, instrument_id: str, side: str) -> dict[str, Any]:
        details = await self.get_instrument_details(instrument_id)
        if not details.get("api_trade_available"):
            raise TBankApiError(f"Instrument {instrument_id} is not tradable via API")
        if side == "BUY" and not details.get("buy_available"):
            raise TBankApiError(f"Instrument {instrument_id} is not available for BUY orders")
        if side == "SELL" and not details.get("sell_available"):
            raise TBankApiError(f"Instrument {instrument_id} is not available for SELL orders")
        if details.get("trading_status") not in _TRADING_STATUS_ALLOWED:
            raise TBankApiError(
                f"Instrument {instrument_id} trading status does not allow market execution: {details.get('trading_status')}"
            )
        return details

    async def get_trading_schedules(
        self,
        *,
        exchange: Optional[str] = None,
        from_dt: datetime,
        to_dt: datetime,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "from": from_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "to": to_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        if exchange:
            payload["exchange"] = exchange
        return await self._rest_post("InstrumentsService/TradingSchedules", payload)

    async def get_portfolio(self, account_id: Optional[str] = None) -> dict[str, Any]:
        acc_id = await self.resolve_account_id(account_id or self.account_id or None)
        return await self._rest_post(self._portfolio_method(), {"accountId": acc_id, "currency": "RUB"})

    async def get_positions(self, account_id: Optional[str] = None) -> dict[str, Any]:
        acc_id = await self.resolve_account_id(account_id or self.account_id or None)
        return await self._rest_post(self._positions_method(), {"accountId": acc_id})

    async def get_withdraw_limits(self, account_id: Optional[str] = None) -> dict[str, Any]:
        acc_id = await self.resolve_account_id(account_id or self.account_id or None)
        return await self._rest_post(self._withdraw_limits_method(), {"accountId": acc_id})

    async def post_market_order(
        self,
        *,
        instrument_id: str,
        quantity_lots: int,
        direction: str,
        order_id: str,
        account_id: Optional[str] = None,
    ) -> dict[str, Any]:
        acc_id = await self.resolve_account_id(account_id or self.account_id or None)
        payload = {
            "instrumentId": instrument_id,
            "quantity": str(int(quantity_lots)),
            "direction": f"ORDER_DIRECTION_{direction}",
            "accountId": acc_id,
            "orderType": "ORDER_TYPE_MARKET",
            "orderId": order_id,
        }
        return await self._rest_post(self._post_order_method(), payload)

    async def post_limit_order(
        self,
        *,
        instrument_id: str,
        quantity_lots: int,
        direction: str,
        limit_price: Decimal,
        order_id: str,
        account_id: Optional[str] = None,
    ) -> dict[str, Any]:
        acc_id = await self.resolve_account_id(account_id or self.account_id or None)
        units, nano = decimal_to_quotation(limit_price)
        payload = {
            "instrumentId": instrument_id,
            "quantity": str(int(quantity_lots)),
            "direction": f"ORDER_DIRECTION_{direction}",
            "accountId": acc_id,
            "orderType": "ORDER_TYPE_LIMIT",
            "price": {"units": str(units), "nano": nano},
            "orderId": order_id,
        }
        return await self._rest_post(self._post_order_method(), payload)

    async def get_order_state(self, order_id: str, account_id: Optional[str] = None) -> dict[str, Any]:
        acc_id = await self.resolve_account_id(account_id or self.account_id or None)
        return await self._rest_post(self._order_state_method(), {"accountId": acc_id, "orderId": order_id})

    async def wait_for_terminal_order_state(
        self,
        *,
        order_id: str,
        timeout_sec: float,
        poll_interval_sec: float,
        account_id: Optional[str] = None,
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout_sec
        last_state: Optional[dict[str, Any]] = None
        while asyncio.get_running_loop().time() < deadline:
            last_state = await self.get_order_state(order_id, account_id=account_id)
            status = last_state.get("executionReportStatus")
            if status in _ORDER_STATUS_TERMINAL:
                return last_state
            await asyncio.sleep(poll_interval_sec)
        raise TBankApiError(
            f"Order {order_id} did not reach terminal status within {timeout_sec:.1f}s"
        )

    async def get_candles(
        self, instrument_id: str, from_dt: datetime, to_dt: datetime, interval_str: str = "1m"
    ) -> List[Dict]:
        instrument_id = normalize_instrument_id(instrument_id)
        details = await self.get_instrument_details(instrument_id)
        uid = details.get("uid")
        if not uid:
            return []

        payload = {
            "instrumentId": uid,
            "from": from_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "to": to_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "interval": _interval_to_rest(interval_str),
        }
        # `from`/`to` already bound the result size for our bootstrap (hours) and
        # polling (minutes) windows, so avoid optional fields that have proven flaky in
        # sandbox/runtime combinations. In particular, T-Bank may reject requests that
        # combine candle source selection with server-side limits.
        try:
            resp = await self._rest_post("MarketDataService/GetCandles", payload)
        except Exception as e:
            logger.error("Error getting candles via REST: %s", e)
            return []

        items = resp.get("candles", []) or []
        candles = [self._convert_rest_candle(c, instrument_id, uid) for c in items]
        candles.sort(key=lambda x: x["time"])
        return candles

    async def stream_marketdata(self, instrument_ids: List[str]) -> AsyncGenerator[Dict, None]:
        normalized_ids = [normalize_instrument_id(i) for i in instrument_ids]
        if self._stream_mode == "rest_poll":
            async for item in self._rest_poll_marketdata(normalized_ids):
                yield item
            return

        _load_grpc_modules()
        backoff = 1
        while True:
            try:
                uids = []
                map_uid_ticker = {}
                unresolved: list[str] = []
                for iid in normalized_ids:
                    try:
                        uid = await self.resolve_instrument(iid)
                    except Exception as exc:
                        unresolved.append(iid)
                        logger.warning("Skipping unresolved instrument %s for stream: %s", iid, exc)
                        continue
                    if uid:
                        uids.append(uid)
                        map_uid_ticker[uid] = iid
                    else:
                        unresolved.append(iid)

                if unresolved:
                    logger.warning("Stream unresolved instruments skipped: %s", ", ".join(unresolved))

                if not uids:
                    logger.warning("No instruments resolved for streaming.")
                    await asyncio.sleep(5)
                    continue

                channel = await self._get_channel()
                stub = marketdata_pb2_grpc.MarketDataStreamServiceStub(channel)

                subscribe_req = marketdata_pb2.MarketDataRequest(
                    subscribe_candles_request=marketdata_pb2.SubscribeCandlesRequest(
                        subscription_action=marketdata_pb2.SUBSCRIPTION_ACTION_SUBSCRIBE,
                        instruments=[
                            marketdata_pb2.CandleInstrument(
                                instrument_id=uid,
                                interval=marketdata_pb2.SUBSCRIPTION_INTERVAL_ONE_MINUTE,
                            )
                            for uid in uids
                        ],
                    )
                )

                async def request_gen():
                    yield subscribe_req
                    while True:
                        await asyncio.sleep(3600)

                stream = stub.MarketDataStream(request_gen(), metadata=self.metadata)
                logger.info(f"Connected to T-Bank stream for {len(uids)} instruments.")
                backoff = 1

                async for resp in stream:
                    if resp.HasField("candle"):
                        c = resp.candle
                        internal_id = map_uid_ticker.get(c.instrument_uid)
                        if internal_id:
                            yield self._convert_stream_candle(c, internal_id, c.instrument_uid)
                    elif resp.HasField("ping"):
                        pass
            except Exception as e:
                if await self._advance_grpc_tls_variant(e):
                    backoff = 1
                    continue
                if self.sandbox or self._stream_mode == "auto":
                    logger.warning(
                        "Falling back to REST candle polling because gRPC stream is unavailable (%s): %s",
                        self._grpc_tls_variant_label,
                        e,
                    )
                    async for item in self._rest_poll_marketdata(normalized_ids):
                        yield item
                    return
                logger.error(
                    "Stream error (%s): %s. Reconnecting in %ss...",
                    self._grpc_tls_variant_label,
                    e,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def _rest_poll_marketdata(self, instrument_ids: List[str]) -> AsyncGenerator[Dict, None]:
        last_seen: dict[str, tuple[int, str, str, str, str, int]] = {}
        logger.info(
            "Using REST candle polling for market data (%s instrument(s), interval=%ss)",
            len(instrument_ids),
            self._stream_poll_interval_sec,
        )
        missing_instruments: set[str] = set()
        while True:
            now_dt = datetime.now(timezone.utc)
            from_dt = now_dt.replace(second=0, microsecond=0) - timedelta(minutes=3)
            for instrument_id in instrument_ids:
                try:
                    candles = await self.get_candles(instrument_id, from_dt, now_dt, interval_str="1m")
                except TBankApiError as exc:
                    if instrument_id not in missing_instruments:
                        logger.warning("Skipping unavailable instrument %s during REST poll: %s", instrument_id, exc)
                        missing_instruments.add(instrument_id)
                    continue
                except Exception as exc:
                    logger.warning("REST poll failed for %s: %s", instrument_id, exc, exc_info=True)
                    continue

                if instrument_id in missing_instruments:
                    missing_instruments.discard(instrument_id)

                if not candles:
                    continue
                candle = candles[-1]
                key = (
                    candle["time"],
                    str(candle["open"]),
                    str(candle["high"]),
                    str(candle["low"]),
                    str(candle["close"]),
                    int(candle.get("volume", 0)),
                )
                if last_seen.get(instrument_id) == key:
                    continue
                last_seen[instrument_id] = key
                yield {
                    **candle,
                    "event_type": "kline",
                    "is_complete": candle.get("is_complete", False),
                }
            await asyncio.sleep(self._stream_poll_interval_sec)

    def normalize_signal_qty_to_lots(self, qty_units: Decimal, lot_size: int) -> int:
        if lot_size <= 0:
            lot_size = 1
        lots = (qty_units / Decimal(lot_size)).to_integral_value(rounding=ROUND_FLOOR)
        return max(1, int(lots))

    def _convert_rest_candle(self, c: dict[str, Any], instrument_id: str, broker_id: str) -> Dict:
        return {
            "instrument_id": instrument_id,
            "broker_id": broker_id,
            "time": _parse_api_timestamp(c.get("time")),
            "open": quotation_dict_to_decimal(c.get("open")),
            "high": quotation_dict_to_decimal(c.get("high")),
            "low": quotation_dict_to_decimal(c.get("low")),
            "close": quotation_dict_to_decimal(c.get("close")),
            "volume": int(c.get("volume") or 0),
            "is_complete": bool(c.get("isComplete", True)),
        }

    def _convert_candle(self, c, instrument_id: str, broker_id: str) -> Dict:
        return {
            "instrument_id": instrument_id,
            "broker_id": broker_id,
            "time": int(c.time.timestamp()) if hasattr(c.time, "timestamp") else 0,
            "open": quotation_to_decimal(c.open),
            "high": quotation_to_decimal(c.high),
            "low": quotation_to_decimal(c.low),
            "close": quotation_to_decimal(c.close),
            "volume": c.volume,
            "is_complete": c.is_complete,
        }

    def _convert_stream_candle(self, c, instrument_id: str, broker_id: str) -> Dict:
        return {
            "instrument_id": instrument_id,
            "broker_id": broker_id,
            "time": int(c.time.timestamp()) if hasattr(c.time, "timestamp") else 0,
            "open": quotation_to_decimal(c.open),
            "high": quotation_to_decimal(c.high),
            "low": quotation_to_decimal(c.low),
            "close": quotation_to_decimal(c.close),
            "volume": c.volume,
            "event_type": "kline",
        }
