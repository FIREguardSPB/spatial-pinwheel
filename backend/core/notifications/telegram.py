from __future__ import annotations
from core.config import get_token
"""
P6-04: TelegramNotifier — уведомления трейдера через Telegram Bot API.

Поддерживаемые события:
  signal_created          — новый сигнал найден
  trade_executed          — сделка открыта
  sl_hit / tp_hit         — стоп-лосс / тейк-профит сработал
  daily_loss_limit_reached— дневной лимит потерь достигнут

Rate limit: не более 20 сообщений/минуту (Telegram API лимит).
Тихие часы: no_notification_hours задаётся в Settings.

Usage:
    notifier = TelegramNotifier.from_config(settings_orm)
    await notifier.send_signal_created(signal_data)
"""

import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# Events that can be toggled in Settings.notification_events
SUPPORTED_EVENTS = {
    "signal_created",
    "trade_executed",
    "sl_hit",
    "tp_hit",
    "daily_loss_limit_reached",
}

_EMOJI = {
    "signal_created": "📡",
    "trade_executed": "✅",
    "sl_hit":         "🛑",
    "tp_hit":         "🎯",
    "daily_loss_limit_reached": "⚠️",
}


class TelegramNotifier:
    """
    Sends Telegram messages via Bot API.
    Respects rate limit (20/min) and quiet hours.
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        enabled_events: set[str] | None = None,
        quiet_hours: list[int] | None = None,   # hours (MSK) when silent
        rate_limit: int = 20,                   # messages per minute
    ):
        self.bot_token = bot_token
        self.chat_id   = chat_id
        self.enabled_events = enabled_events or SUPPORTED_EVENTS
        self.quiet_hours    = set(quiet_hours or [])
        self._send_times: deque[float] = deque(maxlen=rate_limit)
        self._rate_limit = rate_limit

    @classmethod
    def from_config(cls, settings_orm) -> "TelegramNotifier | None":
        """
        Build from Settings ORM row.
        Returns None if token or chat_id missing (notifications disabled).
        """
        token   = get_token("TELEGRAM_BOT_TOKEN") or getattr(settings_orm, "telegram_bot_token", None) or ""
        chat_id = get_token("TELEGRAM_CHAT_ID") or getattr(settings_orm, "telegram_chat_id", None) or ""
        if not token or not chat_id:
            return None

        events_raw  = getattr(settings_orm, "notification_events", "") or ""
        enabled     = set(e.strip() for e in events_raw.split(",") if e.strip()) or SUPPORTED_EVENTS
        quiet_raw   = getattr(settings_orm, "no_notification_hours", "") or ""
        quiet_hours = [int(h) for h in quiet_raw.split(",") if h.strip().isdigit()]

        return cls(bot_token=token, chat_id=chat_id, enabled_events=enabled, quiet_hours=quiet_hours)

    @classmethod
    def from_settings(cls, settings_or_db) -> "TelegramNotifier | None":
        """
        Convenience alias: accepts Settings ORM row OR SQLAlchemy Session.
        If a Session is passed, queries Settings table first.
        """
        from sqlalchemy.orm import Session as _Session
        if isinstance(settings_or_db, _Session):
            from core.storage.models import Settings
            settings_orm = settings_or_db.query(Settings).first()
            if not settings_orm:
                return None
            return cls.from_config(settings_orm)
        return cls.from_config(settings_or_db)

    def _is_quiet_now(self) -> bool:
        """Check if current MSK hour is in quiet hours."""
        if not self.quiet_hours:
            return False
        msk_hour = (datetime.now(timezone.utc) + timedelta(hours=3)).hour
        return msk_hour in self.quiet_hours

    def _rate_ok(self) -> bool:
        """True if we haven't exceeded rate limit in the last 60 seconds."""
        now = time.monotonic()
        # Drop timestamps older than 60s
        while self._send_times and now - self._send_times[0] > 60:
            self._send_times.popleft()
        return len(self._send_times) < self._rate_limit

    async def _send(self, text: str) -> bool:
        """Send raw text to Telegram. Returns True on success."""
        if not self.bot_token or not self.chat_id:
            return False
        if self._is_quiet_now():
            logger.debug("Telegram: quiet hours, skipping notification")
            return False
        if not self._rate_ok():
            logger.warning("Telegram: rate limit reached (20/min)")
            return False

        url = _TELEGRAM_API.format(token=self.bot_token)
        payload = {
            "chat_id":    self.chat_id,
            "text":       text,
            "parse_mode": "HTML",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
            self._send_times.append(time.monotonic())
            return True
        except Exception as e:
            logger.warning("Telegram send failed: %s", e)
            return False

    def _should_notify(self, event: str) -> bool:
        return event in self.enabled_events

    # ── Public API ─────────────────────────────────────────────────────────────

    async def send_signal_created(self, signal: dict[str, Any]) -> bool:
        if not self._should_notify("signal_created"):
            return False
        side  = signal.get("side", "?")
        instr = signal.get("instrument_id", "?")
        entry = signal.get("entry", 0)
        r     = signal.get("r", 0)
        text = (
            f"{_EMOJI['signal_created']} <b>Новый сигнал</b>\n"
            f"Инструмент: <code>{instr}</code>\n"
            f"Направление: <b>{side}</b>\n"
            f"Вход: {float(entry):.4f}  |  R/R: {float(r):.2f}"
        )
        return await self._send(text)

    async def send_trade_executed(self, trade: dict[str, Any]) -> bool:
        if not self._should_notify("trade_executed"):
            return False
        instr = trade.get("instrument_id", "?")
        side  = trade.get("side", "?")
        entry = trade.get("entry_price", 0)
        qty   = trade.get("qty", 0)
        text = (
            f"{_EMOJI['trade_executed']} <b>Сделка открыта</b>\n"
            f"Инструмент: <code>{instr}</code>\n"
            f"Направление: <b>{side}</b>  Qty: {qty}\n"
            f"Вход: {float(entry):.4f}"
        )
        return await self._send(text)

    async def send_sl_hit(self, trade: dict[str, Any]) -> bool:
        if not self._should_notify("sl_hit"):
            return False
        pnl = float(trade.get("realized_pnl", 0))
        text = (
            f"{_EMOJI['sl_hit']} <b>Стоп-лосс сработал</b>\n"
            f"Инструмент: <code>{trade.get('instrument_id', '?')}</code>\n"
            f"P&amp;L: <b>{pnl:+.2f} ₽</b>"
        )
        return await self._send(text)

    async def send_tp_hit(self, trade: dict[str, Any]) -> bool:
        if not self._should_notify("tp_hit"):
            return False
        pnl = float(trade.get("realized_pnl", 0))
        text = (
            f"{_EMOJI['tp_hit']} <b>Тейк-профит взят!</b>\n"
            f"Инструмент: <code>{trade.get('instrument_id', '?')}</code>\n"
            f"P&amp;L: <b>+{pnl:.2f} ₽</b> 🎉"
        )
        return await self._send(text)

    async def send_daily_loss_limit(self, current_loss: float, limit: float) -> bool:
        if not self._should_notify("daily_loss_limit_reached"):
            return False
        text = (
            f"{_EMOJI['daily_loss_limit_reached']} <b>Дневной лимит достигнут</b>\n"
            f"Потери: <b>{current_loss:.2f} ₽</b>  |  Лимит: {limit:.2f} ₽\n"
            f"Бот приостановил торговлю до завтра."
        )
        return await self._send(text)
