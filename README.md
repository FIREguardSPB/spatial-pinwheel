# Spatial Pinwheel 🌀

Автоматический трейдер для MOEX с FastAPI backend, React/Vite frontend, AI-анализом сигналов и risk-management.

## Быстрый старт

### Вариант 1: Docker Compose

```bash
cp .env.example .env
# заполните .env

docker compose -f backend/infra/docker-compose.yml --profile mock up -d --build
```

После старта:
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000/api/v1`
- Health: `http://localhost:8000/api/v1/health`

### Вариант 2: локальный запуск без Docker

Backend:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn apps.api.main:app --reload --port 8000
```

Frontend:
```bash
npm ci
npm run dev
```

## Конфигурация

1. Скопируйте `.env.example` в `.env`.
2. Заполните минимум:
   - `AUTH_TOKEN`
   - `DATABASE_URL`
   - `REDIS_URL`
3. Для AI и Telegram дополнительно заполните:
   - `CLAUDE_API_KEY` / `OPENAI_API_KEY`
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

## Проверки

```bash
# Backend syntax
python -m compileall backend

# Frontend build
npm run build

# Frontend tests
npm run test
```

## Что исправлено в этой версии

- исправлены синтаксические ошибки в `Layout.tsx` и `SettingsPage.tsx`;
- приведены к единому виду API base URLs (`/api/v1`);
- добавлены недостающие env-переменные для AI/Telegram;
- Dockerfile фронтенда переведён на multistage build;
- добавлены healthchecks для frontend и worker в compose;
- theme теперь применяется к `documentElement` и сохраняется в persist-store.
