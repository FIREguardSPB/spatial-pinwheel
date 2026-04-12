# FIX47

- Исправлен dev API target для фронтенда: по умолчанию используется `http://127.0.0.1:8001`, что соответствует обычному локальному запуску API/systemd.
- `apiClient` в dev теперь идёт напрямую на backend, даже если `VITE_DEV_PROXY_TARGET` не задан.
- SSE stream в dev тоже идёт напрямую на backend по `8001` по умолчанию.
- Vite proxy fallback тоже переключён на `8001`.
