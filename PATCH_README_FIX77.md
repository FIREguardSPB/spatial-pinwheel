# FIX77 — Front fail-open / settings crash / shorter request waits

## Что исправлено
- Убран прямой crash в SettingsPage при `status.connection === undefined`.
- SettingsPage больше не ждёт бесконечно и стартует от safe default form state.
- React Query переведён на `retry: false` по умолчанию, чтобы страницы не висели на сериях ретраев.
- Общий axios timeout уменьшен до 3.5с, чтобы failover/fallback срабатывал заметно раньше.
- Health endpoint больше переводит UI в degraded, а не в тотальный global error.
- Decision Log стартует с placeholder данными и не висит пустым.
- Dashboard мини-виджеты и settings hooks теперь имеют initial/placeholder data.
- Часть тяжёлых account/validation запросов завернута в safe catch fallback.

## Зачем
По видео было видно не только backend-degradation, но и чистый frontend-crash в SettingsPage:
`Cannot read properties of undefined (reading 'market_data')`.
Также страницы зависали слишком долго, потому что UI ждал таймаутов и повторных попыток.
