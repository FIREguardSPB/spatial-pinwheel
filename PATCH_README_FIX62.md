# PATCH_README_FIX62

## Какая часть плана закрыта

Это **часть 5 плана** после:
- fix58 — архитектурная стабилизация;
- fix59 — реалистичность trade management;
- fix60 — walk-forward + freshness guard;
- fix61 — allocator 2.0 + nightly recalibration.

В FIX62 закрыт следующий блок:
- **PM-level tuning для auto_paper**;
- **richer exit diagnostics**;
- **длинный paper-audit API/UI**.

## Что изменено

### 1. PM risk throttle
Добавлены runtime-параметры:
- `pm_risk_throttle_enabled`
- `pm_drawdown_soft_limit_pct`
- `pm_drawdown_hard_limit_pct`
- `pm_loss_streak_soft_limit`
- `pm_loss_streak_hard_limit`
- `pm_min_risk_multiplier`

Логика в `core/risk/manager.py` теперь:
- считает portfolio-level multiplier по дневному drawdown,
- учитывает текущий loss streak,
- учитывает давление по exposure относительно risk-cap,
- уменьшает effective risk multiplier при ухудшении торгового дня.

В `worker/processor.py` risk sizing теперь прокладывается в `signal.meta.risk_sizing`,
а при реальном throttle пишется `DecisionLog(type='pm_risk_throttle')`.

### 2. Richer exit diagnostics
Добавлен сервис `core/services/exit_diagnostics.py`.

Теперь при `position_closed` и `adaptive_exit_partial` в payload пишутся:
- `holding_sec`
- `bars_held`
- `hold_limit_bars`
- `hold_utilization_pct`
- `gross_return_pct`
- `net_return_pct`
- `realized_rr_multiple`
- `tp_capture_ratio`
- `slippage_to_requested_close_bps`
- `edge_decay_state`
- `close_quality`

Это даёт не просто PnL выхода, а качество выхода как управленческого решения.

### 3. Paper audit
Добавлен сервис `core/services/paper_audit.py` и endpoint:
- `GET /api/v1/paper/audit?days=30`

Аудит возвращает:
- summary по торговым дням,
- green/red day breakdown,
- PM throttle stats,
- freshness/reallocation/recalibration counters,
- exit diagnostics aggregate,
- edge decay breakdown,
- daily audit rows,
- recommendation list по слабым местам поведения бота.

### 4. UI
Обновлён `AccountPage`:
- добавлен блок **Paper audit 30д**;
- выведены PM multiplier, time-decay exits, TP capture, hold utilization, daily audit table и рекомендации.

Обновлён `SettingsPage`:
- добавлены controls для PM risk throttle.

## Что проверено
- `python -m compileall -q backend`
- `PYTHONPATH=backend python -m unittest backend.tests.test_exit_diagnostics -v`
- изменённые TS/TSX-файлы прогнаны через `typescript.transpileModule`

## Что честно не подтверждено без окружения заказчика
- полный runtime worker/api/db/tbank прогон;
- реальное улучшение PF/expectancy/MDD на длинном paper-run;
- полный frontend production build через установленный node_modules.
