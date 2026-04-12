# FIX74 — frontend transport/runtime stabilization

## Что исправлено

### 1. Убран опасный dev-обход Vite proxy
Раньше фронт в dev сам переписывал `/api/v1` в абсолютный `http://127.0.0.1:8001/api/v1`.
Из-за этого браузер часто бил не туда, особенно при запуске через Docker/WSL/другой host, и UI зависал на `ERR_CONNECTION_REFUSED`.

Теперь:
- относительный `VITE_API_URL=/api/v1` остаётся относительным;
- запросы идут через same-origin / Vite proxy;
- прямой absolute base используется только если он задан явно.

### 2. SSE/stream переведён на тот же runtime-resolver
Поток событий теперь строится через тот же helper, что и HTTP API.
Это убирает расхождение, когда REST и stream смотрели в разные точки.

### 3. Экспорт и debug-панели используют единый resolver
- `TradesPage` теперь открывает export через нормализованный browser URL.
- `SettingsPage` показывает реальную effective API base, а не вводящий в заблуждение raw env value.

### 4. Подчищен фронтовый мусор
- убран дублированный `placeholderData/retry` в dashboard hooks;
- HTTP timeout снижен до 10s, чтобы UI не висел слишком долго на мёртвом endpoint.

## Новая логика env
- `VITE_API_URL=/api/v1` → использовать proxy/same-origin
- `VITE_API_URL=https://host/api/v1` → использовать direct absolute URL
- `VITE_DIRECT_API_BASE_URL=https://host/api/v1` → принудительный direct mode

## Ключевые файлы
- `src/services/runtimeApi.ts`
- `src/services/api.ts`
- `src/services/stream.ts`
- `src/features/trades/TradesPage.tsx`
- `src/features/settings/SettingsPage.tsx`
- `src/features/dashboard/hooks.ts`
