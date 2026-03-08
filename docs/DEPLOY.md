# Инструкция по развёртыванию Spatial Pinwheel (Trading Bot)

## Требования

- Docker 24+ и Docker Compose v2
- 2 ГБ RAM минимум (4 ГБ рекомендуется)
- 5 ГБ дискового пространства
- Для фронтенда (разработка): Node.js 20+

---

## Быстрый старт (локальная разработка)

### 1. Клонировать проект и настроить окружение

```bash
git clone <repo-url> spatial-pinwheel
cd spatial-pinwheel

# Скопировать шаблон переменных окружения
cp .env.example .env
cp backend/infra/.env.example backend/infra/.env
```

### 2. Запустить всё одной командой

```bash
./scripts/deploy.sh mock up
```

Эта команда:
- Собирает Docker-образы (API, Worker, Frontend)
- Поднимает PostgreSQL и Redis
- Запускает миграции БД
- Запускает API (порт 8000), Worker (фоновая обработка), Frontend (порт 5173)

### 3. Открыть в браузере

```
http://localhost:5173
```

В mock-режиме бот генерирует фиктивные данные (цены, сигналы) — никаких реальных денег.

---

## Режимы работы

| Профиль | Команда | Что делает |
|---------|---------|------------|
| `mock` | `./scripts/deploy.sh mock up` | Локальная разработка с mock-данными |
| `tbank_sandbox` | `./scripts/deploy.sh tbank_sandbox up` | T-Bank API в sandbox (тестовый режим) |
| `prod` | `./scripts/deploy.sh prod up` | Production (Внимание: реальные деньги!) |

---

## Конфигурация (.env файл)

### Обязательные переменные

| Переменная | Описание | Пример |
|-----------|----------|--------|
| `APP_ENV` | Окружение | `dev` или `production` |
| `DATABASE_URL` | Подключение к PostgreSQL | `postgresql+psycopg://bot:bot@localhost:5432/botdb` |
| `REDIS_URL` | Подключение к Redis | `redis://localhost:6379/0` |

### Безопасность

| Переменная | Описание | Как сгенерировать |
|-----------|----------|-------------------|
| `AUTH_TOKEN` | Токен доступа к API (обязателен в production) | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `TOKEN_ENCRYPTION_KEY` | Ключ для шифрования API-токенов в БД | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

**Важно:** В production-режиме API не запустится без `AUTH_TOKEN`.

### AI-провайдеры

| Переменная | Описание |
|-----------|----------|
| `CLAUDE_API_KEY` | Ключ API Claude (console.anthropic.com) |
| `OPENAI_API_KEY` | Ключ API OpenAI (platform.openai.com) |
| `DEEPSEEK_API_KEY` | Ключ API DeepSeek Reasoner (api.deepseek.com) |
| `OLLAMA_BASE_URL` | URL локального Ollama (http://localhost:11434) |
| `AI_PRIMARY_PROVIDER` | Основной AI: `claude`, `openai`, `ollama`, `skip` |
| `AI_FALLBACK_PROVIDERS` | Цепочка fallback: `ollama,skip` |

AI-ключи можно также настроить через веб-интерфейс (страница Токены).

### Telegram-уведомления

| Переменная | Описание |
|-----------|----------|
| `TELEGRAM_BOT_TOKEN` | Токен бота (@BotFather) |
| `TELEGRAM_CHAT_ID` | ID чата для уведомлений (@userinfobot) |

### Брокер (T-Bank)

| Переменная | Описание |
|-----------|----------|
| `BROKER_PROVIDER` | `paper` (бумажная торговля) или `tbank` |
| `TBANK_TOKEN` | Токен T-Bank Invest API |
| `TBANK_SANDBOX` | `true` для sandbox, `false` для реальной торговли |
| `TBANK_ACCOUNT_ID` | ID брокерского счёта T-Bank |
| `LIVE_TRADING_ENABLED` | Защитный флаг для включения торговли реальными деньгами |

**Важно:** для реальной торговли укажите `TBANK_TOKEN`, `TBANK_ACCOUNT_ID`, `BROKER_PROVIDER=tbank`, `TBANK_SANDBOX=false` и явно включите `LIVE_TRADING_ENABLED=true`. Без этого `auto_live` не запустится.

---

## Разработка фронтенда (без Docker)

```bash
# Установить зависимости
npm install

# Запустить dev-сервер (порт 5173)
npm run dev

# Сборка для production
npm run build

# Тесты
npm run test
```

Фронтенд в dev-режиме проксирует API-запросы на `http://127.0.0.1:8000` (через Vite proxy).

---

## Разработка бэкенда (без Docker)

```bash
cd backend

# Установить зависимости
pip install -e ".[dev]"

# Запустить PostgreSQL и Redis (нужны отдельно)
# Если используете Docker только для БД:
docker compose -f infra/docker-compose.yml --profile mock up -d postgres redis

# Миграции
alembic upgrade head

# Запуск API
uvicorn apps.api.main:app --reload --port 8000

# Запуск Worker (в другом терминале)
python -m apps.worker.main

# Тесты
pytest tests/ -v
```

---

## Production-деплой на VPS

### 1. Подготовка сервера

```bash
# На сервере (Ubuntu 22.04+)
sudo bash infra/setup-server.sh
```

### 2. Настройка .env

```bash
cd /opt/trading-bot
cp backend/infra/.env.example backend/infra/.env
nano backend/infra/.env
```

Обязательно заполнить: `AUTH_TOKEN`, `TOKEN_ENCRYPTION_KEY`, `POSTGRES_PASSWORD`, `APP_ENV=production`.

### 3. Запуск

```bash
./scripts/deploy.sh prod up
```

### 4. Nginx (внешний reverse proxy)

Конфигурация в `infra/nginx/trading.chatpsy.online.conf`:
- Проксирует `/api/` на API-контейнер (порт 8000)
- Проксирует `/` на Frontend-контейнер (порт 80)
- Блокирует `/metrics` от внешнего доступа

### 5. SSL

Рекомендуется Certbot:
```bash
sudo certbot --nginx -d trading.your-domain.com
```

---

## Управление

| Команда | Действие |
|---------|----------|
| `./scripts/deploy.sh mock up` | Запустить |
| `./scripts/deploy.sh mock down` | Остановить |
| `./scripts/deploy.sh mock logs` | Логи |
| `./scripts/deploy.sh mock restart` | Перезапуск |
| `./scripts/deploy.sh mock status` | Статус |
| `./scripts/deploy.sh mock clean` | Удалить всё (включая БД) |

---

## Мониторинг

```bash
# Добавить Prometheus + Grafana
./scripts/deploy.sh mock up
docker compose -f backend/infra/docker-compose.yml --profile monitoring up -d
```

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3100 (admin / admin)
- Метрики бота: http://localhost:8000/metrics

---

## Обновление

```bash
git pull
./scripts/deploy.sh mock down
./scripts/deploy.sh mock up
```

Миграции БД выполняются автоматически при старте API-контейнера.
