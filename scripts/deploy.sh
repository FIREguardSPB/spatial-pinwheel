#!/bin/bash
# =============================================================================
# Trading Bot - One-Command Deploy Script
# =============================================================================
# Usage:
#   ./scripts/deploy.sh [profile] [action] [args]
#
# Profiles:
#   mock          - Local dev with mock data (default)
#   tbank_sandbox - TBank sandbox integration
#   prod          - Production deployment
#
# Actions:
#   up        - Start all services (default)
#   down      - Stop all services
#   restart   - Restart all services
#   logs      - Show logs
#   status    - Show service status
#   migrate   - Run database migrations only
#   verify    - Run verification script only
#   clean     - Stop services and remove volumes
#   rollback  - Rollback to a specific version tag
#
# Examples:
#   ./scripts/deploy.sh mock up
#   ./scripts/deploy.sh prod rollback v1.1.0
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Defaults
PROFILE="${1:-mock}"
ACTION="${2:-up}"
ROLLBACK_TAG="${3:-}"
COMPOSE_FILE="backend/infra/docker-compose.yml"
ENV_FILE="backend/infra/.env"

# Validate profile
if [[ ! "$PROFILE" =~ ^(mock|tbank_sandbox|prod)$ ]]; then
    echo -e "${RED}Error: Invalid profile '$PROFILE'${NC}"
    echo "Valid profiles: mock, tbank_sandbox, prod"
    exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Trading Bot Deploy${NC}"
echo -e "${BLUE}Profile: ${YELLOW}$PROFILE${NC}"
echo -e "${BLUE}Action:  ${YELLOW}$ACTION${NC}"
echo -e "${BLUE}========================================${NC}"

# Compose command with profile
COMPOSE_CMD="docker compose -f $COMPOSE_FILE --profile $PROFILE"

case "$ACTION" in
    up)
        echo -e "${GREEN}>>> Building images...${NC}"
        $COMPOSE_CMD build
        
        echo -e "${GREEN}>>> Starting database and redis...${NC}"
        $COMPOSE_CMD up -d postgres redis
        
        echo -e "${GREEN}>>> Waiting for database to be healthy...${NC}"
        # Wait for healthcheck instead of fixed sleep
        for i in {1..30}; do
            if $COMPOSE_CMD exec -T postgres pg_isready -U ${POSTGRES_USER:-bot} -d ${POSTGRES_DB:-botdb} > /dev/null 2>&1; then
                echo -e "${GREEN}Database ready!${NC}"
                break
            fi
            echo "Waiting for database... ($i/30)"
            sleep 1
        done
        
        echo -e "${GREEN}>>> Running database migrations...${NC}"
        $COMPOSE_CMD run --rm api python scripts/update_schema.py || {
            echo -e "${YELLOW}Migration script not found or failed, trying alembic...${NC}"
            $COMPOSE_CMD run --rm api alembic upgrade head 2>/dev/null || true
        }
        
        echo -e "${GREEN}>>> Starting all services...${NC}"
        $COMPOSE_CMD up -d
        
        echo -e "${GREEN}>>> Waiting for API to be ready...${NC}"
        # Wait for API healthcheck
        for i in {1..30}; do
            if curl -sf http://localhost:${API_PORT:-3000}/api/v1/health > /dev/null 2>&1; then
                echo -e "${GREEN}API ready!${NC}"
                break
            fi
            echo "Waiting for API... ($i/30)"
            sleep 1
        done
        
        echo -e "${GREEN}>>> Running verification...${NC}"
        $COMPOSE_CMD exec -T api python scripts/verify_settings_integration.py || {
            echo -e "${YELLOW}Verification script failed or not found${NC}"
        }
        
        echo -e "${GREEN}>>> Services started!${NC}"
        $COMPOSE_CMD ps
        
        echo -e "\n${GREEN}========================================${NC}"
        echo -e "${GREEN}Endpoints:${NC}"
        echo -e "  API:      http://localhost:${API_PORT:-3000}/api/v1/health"
        if [[ "$PROFILE" == "prod" ]]; then
            echo -e "  Frontend: http://localhost:${FRONTEND_PORT:-80}"
        fi
        echo -e "${GREEN}========================================${NC}"
        ;;
        
    down)
        echo -e "${YELLOW}>>> Stopping services...${NC}"
        $COMPOSE_CMD down
        echo -e "${GREEN}>>> Services stopped${NC}"
        ;;
        
    restart)
        echo -e "${YELLOW}>>> Restarting services...${NC}"
        $COMPOSE_CMD restart
        echo -e "${GREEN}>>> Services restarted${NC}"
        $COMPOSE_CMD ps
        ;;
        
    logs)
        $COMPOSE_CMD logs -f --tail=100
        ;;
        
    status)
        $COMPOSE_CMD ps
        echo ""
        echo -e "${BLUE}>>> Health Check:${NC}"
        curl -s http://localhost:${API_PORT:-3000}/api/v1/health | python -m json.tool 2>/dev/null || echo "API not responding"
        ;;
        
    migrate)
        echo -e "${GREEN}>>> Running database migrations...${NC}"
        $COMPOSE_CMD exec -T api python scripts/update_schema.py
        echo -e "${GREEN}>>> Migrations complete${NC}"
        ;;
        
    verify)
        echo -e "${GREEN}>>> Running verification...${NC}"
        $COMPOSE_CMD exec -T api python scripts/verify_settings_integration.py
        ;;
        
    clean)
        echo -e "${RED}>>> Stopping services and removing volumes...${NC}"
        read -p "Are you sure? This will delete all data! (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            $COMPOSE_CMD down -v
            echo -e "${GREEN}>>> Cleanup complete${NC}"
        else
            echo -e "${YELLOW}>>> Cancelled${NC}"
        fi
        ;;
        
    rollback)
        if [[ -z "$ROLLBACK_TAG" ]]; then
            echo -e "${RED}Error: Rollback requires a version tag${NC}"
            echo "Usage: ./scripts/deploy.sh $PROFILE rollback <tag>"
            echo "Example: ./scripts/deploy.sh prod rollback v1.1.0"
            exit 1
        fi
        
        echo -e "${YELLOW}>>> Rolling back to $ROLLBACK_TAG...${NC}"
        
        # Determine image registry (from env or default)
        REGISTRY=${REGISTRY:-ghcr.io}
        REPO=${REPO:-owner/repo}
        
        # Update image tags
        export API_IMAGE="${REGISTRY}/${REPO}-api:${ROLLBACK_TAG}"
        export WORKER_IMAGE="${REGISTRY}/${REPO}-worker:${ROLLBACK_TAG}"
        export FRONTEND_IMAGE="${REGISTRY}/${REPO}-frontend:${ROLLBACK_TAG}"
        
        echo -e "${BLUE}Images:${NC}"
        echo "  API:      $API_IMAGE"
        echo "  Worker:   $WORKER_IMAGE"
        echo "  Frontend: $FRONTEND_IMAGE"
        
        # Confirm rollback
        read -p "Proceed with rollback? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}>>> Rollback cancelled${NC}"
            exit 0
        fi
        
        echo -e "${GREEN}>>> Pulling images...${NC}"
        $COMPOSE_CMD pull api worker frontend 2>/dev/null || $COMPOSE_CMD pull api worker
        
        echo -e "${GREEN}>>> Restarting services...${NC}"
        $COMPOSE_CMD up -d --no-build
        
        echo -e "${GREEN}>>> Waiting for API to be ready...${NC}"
        for i in {1..30}; do
            if curl -sf http://localhost:${API_PORT:-3000}/api/v1/health > /dev/null 2>&1; then
                echo -e "${GREEN}API ready!${NC}"
                break
            fi
            echo "Waiting for API... ($i/30)"
            sleep 1
        done
        
        echo -e "${GREEN}>>> Running verification...${NC}"
        $COMPOSE_CMD exec -T api python scripts/verify_settings_integration.py || {
            echo -e "${YELLOW}Verification failed - consider rolling back further${NC}"
        }
        
        echo -e "${GREEN}>>> Rollback complete!${NC}"
        $COMPOSE_CMD ps
        
        # Show health
        echo -e "\n${BLUE}>>> Health Check:${NC}"
        curl -s http://localhost:${API_PORT:-3000}/api/v1/health | python -m json.tool 2>/dev/null || echo "API not responding"
        ;;
        
    *)
        echo -e "${RED}Error: Unknown action '$ACTION'${NC}"
        echo "Valid actions: up, down, restart, logs, status, migrate, verify, clean, rollback"
        exit 1
        ;;
esac
