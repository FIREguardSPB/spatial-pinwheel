# Release Runbook

## Overview

This document describes how to release, verify, and rollback the Trading Bot application.

## Prerequisites

- Docker and Docker Compose installed
- Git access to the repository
- (For CD) GitHub Secrets configured:
  - `DEPLOY_HOST` - Server hostname/IP
  - `DEPLOY_USER` - SSH username
  - `DEPLOY_SSH_KEY` - Private SSH key
  - `DEPLOY_PATH` - Path to project on server
  - `DEPLOY_URL` - Public URL (e.g., `https://bot.example.com`)

## Release Process

### 1. Create Release Tag

```bash
# Ensure you're on main branch with latest changes
git checkout main
git pull origin main

# Create annotated tag
git tag -a v1.2.0 -m "v1.2.0: Description of changes"

# Push tag (triggers CD pipeline)
git push origin v1.2.0
```

### 2. Automated CD Pipeline

When a tag is pushed, GitHub Actions will:
1. Build Docker images (api, worker, frontend)
2. Push to GitHub Container Registry (ghcr.io)
3. SSH to server and deploy
4. Run migrations
5. Verify deployment

### 3. Manual Deployment (Alternative)

```bash
# On the server
cd /path/to/project

# Option A: Use deploy script
./scripts/deploy.sh prod up

# Option B: Manual docker compose
docker compose -f backend/infra/docker-compose.yml --profile prod pull
docker compose -f backend/infra/docker-compose.yml --profile prod up -d
```

## Verification

### Health Check

```bash
curl http://localhost:3000/api/v1/health
```

Expected response:
```json
{
  "status": "ok",
  "version": "1.2.0",
  "commit": "abc1234",
  "ts": 1234567890000,
  "broker": {
    "provider": "mock",
    "sandbox": false,
    "status": "connected"
  }
}
```

### Settings Integration Test

```bash
# Inside container
docker compose exec api python scripts/verify_settings_integration.py

# Or externally
curl http://localhost:3000/api/v1/settings
```

### Full Status Check

```bash
./scripts/deploy.sh prod status
```

### Log Inspection

```bash
# All services
./scripts/deploy.sh prod logs

# Specific service
docker compose -f backend/infra/docker-compose.yml logs -f api
docker compose -f backend/infra/docker-compose.yml logs -f worker
```

## Rollback

### Quick Rollback (Script)

```bash
# Rollback to specific version
./scripts/deploy.sh prod rollback v1.1.0
```

This will:
1. Update image tags to the specified version
2. Pull the old images
3. Restart services (no build)
4. Verify deployment

### Manual Rollback

```bash
# 1. Set environment variables
export API_IMAGE=ghcr.io/owner/repo-api:v1.1.0
export WORKER_IMAGE=ghcr.io/owner/repo-worker:v1.1.0
export FRONTEND_IMAGE=ghcr.io/owner/repo-frontend:v1.1.0

# 2. Pull and restart
docker compose -f backend/infra/docker-compose.yml --profile prod pull
docker compose -f backend/infra/docker-compose.yml --profile prod up -d

# 3. Verify
curl http://localhost:3000/api/v1/health
```

### Database Rollback (Caution!)

If database migrations need to be reverted:

```bash
# Check current migration
docker compose exec api alembic current

# Downgrade one step
docker compose exec api alembic downgrade -1

# Or to specific revision
docker compose exec api alembic downgrade <revision_id>
```

> **Warning:** Database rollbacks may cause data loss. Always backup first.

## Troubleshooting

### Services Won't Start

```bash
# Check container status
docker compose ps -a

# Check logs for errors
docker compose logs api --tail=50
docker compose logs worker --tail=50

# Check database connection
docker compose exec api python -c "from core.storage.session import engine; print(engine.connect())"
```

### Health Check Fails

1. Check if API container is running: `docker compose ps api`
2. Check API logs: `docker compose logs api`
3. Check database is healthy: `docker compose ps postgres`
4. Check Redis is healthy: `docker compose ps redis`

### Worker Not Processing Signals

```bash
# Check worker logs
docker compose logs worker --tail=100

# Check Redis connection
docker compose exec redis redis-cli ping

# Check if worker is subscribed
docker compose exec redis redis-cli pubsub channels
```

### Migration Failed

```bash
# Check migration status
docker compose exec api alembic current
docker compose exec api alembic history

# Run migrations manually
docker compose run --rm api python scripts/update_schema.py
```

## Checklist

### Pre-Release
- [ ] All tests passing (`npm run lint`, `pytest`)
- [ ] Version updated in `package.json` and `core/version.py`
- [ ] CHANGELOG updated (if exists)
- [ ] PR approved and merged to main

### Post-Release
- [ ] Tag pushed and CD pipeline completed
- [ ] Health check returns 200
- [ ] Settings endpoint responds correctly
- [ ] Worker is running and processing signals
- [ ] Frontend loads correctly (if prod profile)
- [ ] No errors in logs (first 5 minutes)

### Rollback Triggers
- Health check fails for > 2 minutes
- Worker throwing continuous errors
- Database connection errors
- User-reported critical bugs
