FIX42 — adaptive symbol engine

Что добавлено:
- Перевод от общих порогов к профилям по каждой бумаге.
- Файловое хранилище symbol profiles: docs/symbol_profiles.runtime.json
- AdaptiveSymbolPlan: per-symbol regime, strategy, threshold, hold bars, reentry cooldown, risk multiplier.
- Worker теперь выбирает стратегию по бумаге и режиму рынка перед анализом.
- DecisionEngine использует per-symbol adaptive threshold.
- PositionMonitor использует adaptive hold bars из сигнала, а не только глобальный time_stop_bars.
- RiskManager учитывает per-symbol risk_multiplier и reentry cooldown.
- API: GET/PUT /api/v1/symbol-profiles, GET /api/v1/symbol-profiles/{instrument_id}.

Что это НЕ делает:
- это не автономный “идеальный трейдер”;
- LM не получает права напрямую крутить прод-риски без ограничений;
- это первый реальный слой per-symbol adaptive engine, на который уже можно тестово наращивать дальнейшую логику.
