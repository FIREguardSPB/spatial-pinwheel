# FIX23 — expectancy / levels / AI hard-block safety

## Что исправлено

- Добавлена декомпозиция cost/expectancy в Decision Engine metrics:
  - `gross_rr`
  - `net_rr`
  - `raw_profit`
  - `raw_loss`
  - `round_trip_cost`
  - `net_profit`
  - `net_loss`
  - `costs_fee_bps`
  - `costs_slippage_bps`
- Исправлена семантика сообщений по Net RR:
  - `Non-positive after costs` только если `net_rr <= 0`
  - `Sub-1 after costs` если `0 < net_rr < 1`
  - `Below target after costs` если `1 <= net_rr < 1.5`
- Добавлен safety gate:
  - `net_rr <= 0` → `REJECT`
  - `0 < net_rr < 1` и score даёт `TAKE` → кап на `SKIP`
- AI больше не может override-ить hard-block решение DE.
- Поиск opposing levels усилен:
  - lookback расширен до 55 баров
  - добавлен tolerance fallback
  - в metrics пишутся `level_lookback_bars`, `level_search_tolerance`, `level_source`
- Смягчён шумный volume-spike фильтр:
  - warn threshold поднят до `8x`
  - extreme threshold `20x`
  - пороги пишутся в metrics
- Сообщение `Stop distance suspicious` теперь показывает ожидаемый ATR-диапазон.
- Выровнены frontend/backend defaults для `atr_stop_soft_max = 2.5`.

## Что проверено

- `python3 -m compileall -q backend src`
- Дополнительные локальные runtime-проверки decision-quality логики:
  - sub-1 net RR больше не помечается как negative
  - non-positive net RR блокирует исполнение
  - widened level lookup находит более дальние opposing levels
  - AI override не пробивает DE hard block
