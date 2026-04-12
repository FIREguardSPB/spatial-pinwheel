# Global audit FIX78 — frontend/backend interaction

## Главный вывод

Проблема проекта была не в одной-двух поломанных страницах, а в том, что frontend перестал быть тонким клиентом к backend.

Старая версия фронта:
- дублировала запросы на один и тот же ресурс;
- использовала разные query keys для одного и того же endpoint;
- имела слишком много тяжёлых параллельных загрузок на страницу;
- пыталась "лечить" backend ошибки глобальными fallbacks;
- смешивала page state, widget state и transport state;
- зависела от глобального stream connect уже на старте приложения.

## Что признано backend-истиной

В FIX78 фронт построен вокруг следующих backend endpoints как первичных:

- `GET /bot/status`
- `GET /state`
- `GET /worker/status`
- `GET /settings`
- `GET /settings/trading-schedule`
- `GET /watchlist`
- `GET /state/positions`
- `GET /state/orders`
- `GET /state/trades`
- `GET /signals`
- `GET /decision-log`
- `GET /account/summary`
- `GET /account/history`
- `GET /account/daily-stats`
- `GET /backtest/strategies`
- `POST /backtest`

## Критические причины неработоспособности старого фронта

1. Query storm на старте страниц.
2. Расхождение query keys для одинаковых endpoint.
3. Глобальный stream connect создавал лишний шум уже на bootstrap.
4. Settings и Dashboard были перегружены тяжёлыми зависимостями.
5. Health трактовался слишком жёстко и ронял UI даже в paper-режиме.
6. Ошибки GET слишком часто превращались в глобальный banner/toast вместо локального page error.

## Что сделано

- frontend-shell переписан в сторону page-level data loading;
- основные страницы сделаны заново поверх общего query layer;
- removed "always-on" stream bootstrap;
- упрощён transport error policy;
- backend health semantics ослаблена для paper/review режима.

## Остаточные риски

1. Если реальные backend routes сами падают 500, страницы покажут локальную ошибку, но не смогут изобразить рабочие данные.
2. Старые неиспользуемые компоненты всё ещё лежат в проекте; они не участвуют в новой логике, но технический долг остаётся.
3. Некоторые advanced analytics screens намеренно не были возвращены в новый UI, чтобы сначала добиться базовой работоспособности.

## Следующий правильный шаг

После проверки FIX78 — добивать уже не shell, а конкретные backend 500 по логам, если они останутся.
