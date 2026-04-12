# FIX25 — intraday AI prompt refactor for scalp mode

## Что изменено
- AI prompt переведён в режим `scalp-first`: техника, VWAP, volume, Net RR и volatility стали приоритетом.
- Статичные макро-факторы больше не используются как автоматический блокер сигнала.
- Ставка ЦБ и общий геополитический фон теперь попадают в prompt только если есть **свежий динамический catalyst**.
- Добавлен слой `relevance.py`, который определяет, когда rate / geo / FX контекст действительно релевантен для intraday.
- Sector-aware context переработан под скальпинг: отраслевые драйверы сохранены, но без постоянного макрошума.
- В prompt добавлены свежие корпоративные/секторные новости за 24 часа и явная инструкция не блокировать сильную технику статичным фоном.
- Для A/B и дебага добавлен `ai_prompt_profile = intraday_dynamic_v1`.
- По умолчанию `ai_min_confidence` снижен до `55` (backend, frontend, migration).
- В лог AI decisions теперь передаётся фактический prompt text для расчёта `prompt_hash`.

## Что проверено
- `python3 -m compileall -q backend src`
- `PYTHONPATH=backend pytest -q backend/tests/test_ai_context_improvements.py`

## Что не подтверждено в песочнице
- Полный runtime-прогон у заказчика.
- Полный frontend npm build.
- Полный pytest suite (в контейнере нет части зависимостей проекта, включая SQLAlchemy).
