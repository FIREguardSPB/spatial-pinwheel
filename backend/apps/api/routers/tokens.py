"""
P8-01: API-токены — управление из UI.

Endpoints:
  GET    /v1/tokens          — список всех токенов (значения замаскированы)
  POST   /v1/tokens          — добавить / обновить токен
  PUT    /v1/tokens/{id}     — обновить токен
  DELETE /v1/tokens/{id}     — удалить токен
  GET    /v1/tokens/reveal/{id} — получить полное значение (требует confirm=true)
  POST   /v1/tokens/test/{id}   — проверить токен (ping-тест для Telegram/Claude/OpenAI)

Маскирование: показываем первые 4 и последние 4 символа, остальное — звёздочки.
  "sk-ant-api03-XXXXXXXXXXXXXXXX..." → "sk-a****XXXX"
"""
from __future__ import annotations

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.deps import verify_token
from core.storage.session import get_db
from core.storage.models import ApiToken
from core.utils.time import now_ms

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_token)])

# ── Pre-defined known token keys ──────────────────────────────────────────────
KNOWN_TOKENS: list[dict] = [
    {
        "key_name":    "AUTH_TOKEN",
        "label":       "Auth Token (доступ к API)",
        "description": "Bearer-токен для авторизации запросов к API бота. "
                        "Фронтенд передаёт его в заголовке Authorization.",
        "category":    "auth",
    },
    {
        "key_name":    "CLAUDE_API_KEY",
        "label":       "Claude API Key (Anthropic)",
        "description": "API-ключ для AI-анализа сигналов через Claude Sonnet/Opus. "
                        "Получить: console.anthropic.com",
        "category":    "ai",
    },
    {
        "key_name":    "OPENAI_API_KEY",
        "label":       "OpenAI API Key",
        "description": "API-ключ для AI-анализа через GPT-4o. "
                        "Получить: platform.openai.com",
        "category":    "ai",
    },
    {
        "key_name":    "TELEGRAM_BOT_TOKEN",
        "label":       "Telegram Bot Token",
        "description": "Токен бота для отправки уведомлений о сигналах и сделках. "
                        "Получить: @BotFather в Telegram.",
        "category":    "telegram",
    },
    {
        "key_name":    "TELEGRAM_CHAT_ID",
        "label":       "Telegram Chat ID",
        "description": "ID чата/канала для уведомлений. "
                        "Узнать: переслать сообщение боту @userinfobot.",
        "category":    "telegram",
    },
    {
        "key_name":    "TBANK_ACCOUNT_ID",
        "label":       "T-Bank Account ID",
        "description": "Идентификатор брокерского счёта T-Bank для live-торговли. Нужен вместе с TBANK_TOKEN.",
        "category":    "broker",
    },
    {
        "key_name":    "TBANK_TOKEN",
        "label":       "T-Bank Invest Token",
        "description": "Токен T-Bank Investments API для реальной торговли на MOEX. "
                        "Получить: tbank.ru → Инвестиции → API.",
        "category":    "broker",
    },
    {
        "key_name":    "OLLAMA_BASE_URL",
        "label":       "Ollama Base URL",
        "description": "URL локального инстанса Ollama (по умолчанию http://localhost:11434). "
                        "Используется для локальных LLM (DeepSeek, Qwen).",
        "category":    "ai",
    },
]

KNOWN_KEY_NAMES = {t["key_name"] for t in KNOWN_TOKENS}


# ── Schemas ───────────────────────────────────────────────────────────────────
class TokenCreate(BaseModel):
    key_name:    str
    value:       str
    label:       str = ""
    description: str = ""
    category:    str = "general"


class TokenUpdate(BaseModel):
    value:       str | None = None
    label:       str | None = None
    description: str | None = None
    is_active:   bool | None = None


class TokenOut(BaseModel):
    id:           str
    key_name:     str
    masked_value: str          # never the real value
    label:        str
    description:  str
    category:     str
    is_active:    bool
    has_value:    bool         # True if value is non-empty
    created_ts:   int
    updated_ts:   int
    last_used_ts: int | None


# ── Masking ───────────────────────────────────────────────────────────────────
def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "****" + value[-4:]


def _decrypt_value(raw: str) -> str:
    """Decrypt token value from DB (P8-02). Returns plaintext."""
    if not raw:
        return ""
    try:
        from core.security.crypto import decrypt_token
        return decrypt_token(raw)
    except Exception:
        return raw


def _encrypt_value(plaintext: str) -> str:
    """Encrypt token value for DB storage (P8-02). Returns ciphertext or plaintext."""
    if not plaintext:
        return ""
    try:
        from core.security.crypto import encrypt_token
        return encrypt_token(plaintext)
    except Exception:
        return plaintext


def _to_out(tok: ApiToken) -> TokenOut:
    plain = _decrypt_value(tok.value)
    return TokenOut(
        id=tok.id,
        key_name=tok.key_name,
        masked_value=_mask(plain),
        label=tok.label or tok.key_name,
        description=tok.description or "",
        category=tok.category or "general",
        is_active=bool(tok.is_active),
        has_value=bool(plain),
        created_ts=tok.created_ts or 0,
        updated_ts=tok.updated_ts or 0,
        last_used_ts=tok.last_used_ts,
    )


# ── Helpers: fill known defaults when DB is empty ────────────────────────────
def _ensure_known_tokens(db: Session) -> None:
    """Create placeholder rows for known token types if not yet present."""
    existing = {t.key_name for t in db.query(ApiToken.key_name).all()}
    for meta in KNOWN_TOKENS:
        if meta["key_name"] not in existing:
            db.add(ApiToken(
                id=f"tok_{uuid.uuid4().hex[:8]}",
                key_name=meta["key_name"],
                value="",
                label=meta["label"],
                description=meta["description"],
                category=meta["category"],
                is_active=True,
                created_ts=now_ms(),
                updated_ts=now_ms(),
            ))
    db.commit()


# ── Routes ────────────────────────────────────────────────────────────────────
@router.get("", response_model=list[TokenOut], summary="Список токенов (значения замаскированы)")
def list_tokens(db: Session = Depends(get_db)):
    _ensure_known_tokens(db)
    tokens = db.query(ApiToken).order_by(ApiToken.category, ApiToken.key_name).all()
    return [_to_out(t) for t in tokens]


@router.post("", response_model=TokenOut, status_code=201,
             summary="Добавить или обновить токен")
def upsert_token(body: TokenCreate, db: Session = Depends(get_db)):
    existing = db.query(ApiToken).filter(ApiToken.key_name == body.key_name).first()
    if existing:
        existing.value = _encrypt_value(body.value)
        existing.updated_ts = now_ms()
        if body.label:       existing.label = body.label
        if body.description: existing.description = body.description
        if body.category:    existing.category = body.category
        db.commit()
        db.refresh(existing)
        logger.info("Token updated: %s", body.key_name)
        return _to_out(existing)

    # New token
    new_tok = ApiToken(
        id=f"tok_{uuid.uuid4().hex[:8]}",
        key_name=body.key_name,
        value=_encrypt_value(body.value),
        label=body.label or body.key_name,
        description=body.description,
        category=body.category,
        is_active=True,
        created_ts=now_ms(),
        updated_ts=now_ms(),
    )
    db.add(new_tok)
    db.commit()
    db.refresh(new_tok)
    logger.info("Token created: %s", body.key_name)
    return _to_out(new_tok)


@router.put("/{token_id}", response_model=TokenOut, summary="Обновить токен")
def update_token(token_id: str, body: TokenUpdate, db: Session = Depends(get_db)):
    tok = db.query(ApiToken).filter(ApiToken.id == token_id).first()
    if not tok:
        raise HTTPException(404, "Token not found")
    if body.value       is not None: tok.value = _encrypt_value(body.value)
    if body.label       is not None: tok.label = body.label
    if body.description is not None: tok.description = body.description
    if body.is_active   is not None: tok.is_active = body.is_active
    tok.updated_ts = now_ms()
    db.commit()
    db.refresh(tok)
    return _to_out(tok)


@router.delete("/{token_id}", summary="Удалить токен")
def delete_token(token_id: str, db: Session = Depends(get_db)):
    tok = db.query(ApiToken).filter(ApiToken.id == token_id).first()
    if not tok:
        raise HTTPException(404, "Token not found")
    # Prevent deleting known system tokens (only clear value)
    if tok.key_name in KNOWN_KEY_NAMES:
        tok.value = ""
        tok.updated_ts = now_ms()
        db.commit()
        logger.info("Token value cleared: %s", tok.key_name)
        return {"cleared": True, "key_name": tok.key_name}
    db.delete(tok)
    db.commit()
    logger.info("Token deleted: %s", tok.key_name)
    return {"deleted": True, "id": token_id}


@router.get("/reveal/{token_id}", summary="Получить полное значение токена")
def reveal_token(
    token_id: str,
    confirm: bool = Query(default=False, description="Должен быть true"),
    db: Session = Depends(get_db),
):
    if not confirm:
        raise HTTPException(400, "Pass ?confirm=true to reveal token value")
    tok = db.query(ApiToken).filter(ApiToken.id == token_id).first()
    if not tok:
        raise HTTPException(404, "Token not found")
    # Update last_used_ts
    tok.last_used_ts = now_ms()
    db.commit()
    return {"id": token_id, "key_name": tok.key_name, "value": _decrypt_value(tok.value)}


@router.post("/test/{token_id}", summary="Проверить токен (ping-тест)")
async def test_token(token_id: str, db: Session = Depends(get_db)):
    tok = db.query(ApiToken).filter(ApiToken.id == token_id).first()
    if not tok:
        raise HTTPException(404, "Token not found")
    plain_value = _decrypt_value(tok.value)
    if not plain_value:
        return {"ok": False, "message": "Token value is empty"}

    tok.last_used_ts = now_ms()
    db.commit()

    # ── Telegram test ──────────────────────────────────────────────────────────
    if tok.key_name == "TELEGRAM_BOT_TOKEN":
        import httpx
        try:
            resp = httpx.get(
                f"https://api.telegram.org/bot{plain_value}/getMe",
                timeout=8.0,
            )
            data = resp.json()
            if data.get("ok"):
                return {"ok": True, "message": f"Bot: @{data['result']['username']}"}
            return {"ok": False, "message": data.get("description", "Unknown error")}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    # ── Claude test ────────────────────────────────────────────────────────────
    if tok.key_name == "CLAUDE_API_KEY":
        import httpx
        try:
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": plain_value,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 8,
                    "messages": [{"role": "user", "content": "ping"}],
                },
                timeout=10.0,
            )
            if resp.status_code == 200:
                return {"ok": True, "message": "Claude API: connected ✓"}
            return {"ok": False, "message": f"HTTP {resp.status_code}: {resp.text[:100]}"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    # ── OpenAI test ────────────────────────────────────────────────────────────
    if tok.key_name == "OPENAI_API_KEY":
        import httpx
        try:
            resp = httpx.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {plain_value}"},
                timeout=8.0,
            )
            if resp.status_code == 200:
                return {"ok": True, "message": "OpenAI API: connected ✓"}
            return {"ok": False, "message": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    # ── T-Bank test ────────────────────────────────────────────────────────────
    if tok.key_name == "TBANK_TOKEN":
        import httpx
        try:
            resp = httpx.post(
                "https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1.UsersService/GetAccounts",
                headers={
                    "Authorization": f"Bearer {plain_value}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={},
                timeout=10.0,
            )
            if resp.status_code != 200:
                return {"ok": False, "message": f"HTTP {resp.status_code}: {resp.text[:120]}"}
            data = resp.json()
            accounts = data.get("accounts", [])
            return {"ok": True, "message": f"T-Bank API: found {len(accounts)} account(s)"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    # Generic: just confirm value is non-empty
    return {"ok": True, "message": f"{tok.key_name}: value is set ({len(plain_value)} chars)"}
