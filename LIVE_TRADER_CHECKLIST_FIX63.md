# Жёсткий чек-лист критериев живого опытного трейдера

## Пороговые критерии

- Profit Factor >= 1.30 — минимум, >= 1.50 — хорошо
- Expectancy per trade > 0 — минимум, >= 0.15R — хорошо
- Max Drawdown <= 8% на paper equity — хорошо, <= 12% — допустимо
- Win rate by regime не должен разваливаться: в каждом ключевом режиме >= 45% либо PF >= 1.20
- Stability: минимум 4 из 5 последних недель зелёные
- Execution quality: realized/MFE capture >= 0.45, avg adverse slippage controlled, execution errors ~= 0
- Risk discipline: ни одного дня за лимитом daily loss без throttle response
- Portfolio discipline: концентрация крупнейшей позиции обычно <= 25-30% open book

## Статус FIX63

- Profit Factor: частично — метрика есть, но длинной статистики ещё нет
- Expectancy: частично — метрика есть, но не доказана по длинному run
- Max Drawdown: частично — метрика есть, но нужен run
- Hit rate by regime: не выполнено полностью — regime-aware analytics есть не в полном объёме
- Stability week-over-week: не выполнено — нужен бумажный прогон по неделям
- Execution quality: частично — есть slippage, MFE/MAE, capture ratio, execution errors
- Risk discipline: выполнено частично — PM throttle и overlay есть
- Portfolio discipline: частично — optimizer 2.0 есть, но это ещё не full optimizer класса production prop desk
