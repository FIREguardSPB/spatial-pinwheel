# PATCH README — FIX19

## Что добавлено сверх FIX18

### Backend / AI / данные
- Добавлена устойчивая fallback-цепочка для Brent: Yahoo quote -> Yahoo RSS -> Investing -> MarketWatch.
- Расширен сбор новостей для AI: к RSS RBC/Investing добавлены публичные страницы Reuters (Business/Markets/Energy/World).
- Усилен geo/macro-контекст:
  - выделение тематик (санкции, война/конфликт, нефть/логистика, ставки/инфляция, пошлины/торговля)
  - более содержательный расчёт `geopolitical_risk`
  - темы теперь передаются в prompt для AI

### Frontend / UX / стабильность
- Убран overlay-конфликт `SYSTEM ONLINE` с кнопками в правом верхнем углу дашборда: статус перенесён в обычный поток header.
- Панель `Ручной ордер` теперь сворачивается/разворачивается, состояние сохраняется в localStorage.
- Исправлен баг со статусом бота в Settings:
  - больше нет ложного начального `is_running=false` из initialData
  - status query теперь принудительно refetch'ится при входе на страницу
  - в UI показывается состояние загрузки статуса вместо неверного "выключен"
- При старте/остановке бота SettingsPage больше не делает лишний промежуточный PUT настроек перед `/bot/start|stop`.
- Снижена шумность фронта:
  - React Query Devtools только в DEV
  - убраны лишние `console.log` по stream/chart

## Что проверено
- `python3 -m compileall -q backend` — OK
