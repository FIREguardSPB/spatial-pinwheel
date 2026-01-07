#!/bin/bash
# =============================================================================
# Trading Bot - Server Setup Script
# Run once on fresh Ubuntu 24.04 LTS server
# Usage: sudo bash setup-server.sh
# =============================================================================

set -e

echo "=========================================="
echo "Trading Bot Server Setup"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# -----------------------------------------------------------------------------
# 1. System Updates
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[1/8] Updating system packages...${NC}"
apt update && apt upgrade -y

# -----------------------------------------------------------------------------
# 2. Install Python 3.11
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[2/8] Installing Python 3.11...${NC}"
apt install -y software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt update
apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# -----------------------------------------------------------------------------
# 3. Install Node.js 20 (for frontend build)
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[3/8] Installing Node.js 20...${NC}"
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

# -----------------------------------------------------------------------------
# 4. Install PostgreSQL 16
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[4/8] Installing PostgreSQL 16...${NC}"
apt install -y postgresql postgresql-contrib

# Create trading database and user
sudo -u postgres psql <<EOF
CREATE USER trading WITH PASSWORD 'trading_secure_password_change_me';
CREATE DATABASE trading_bot OWNER trading;
GRANT ALL PRIVILEGES ON DATABASE trading_bot TO trading;
EOF

# -----------------------------------------------------------------------------
# 5. Install Redis
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[5/8] Installing Redis...${NC}"
apt install -y redis-server
systemctl enable redis-server
systemctl start redis-server

# -----------------------------------------------------------------------------
# 6. Create Directory Structure
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[6/8] Creating directory structure...${NC}"
mkdir -p /var/www/trading/backend
mkdir -p /var/www/trading/frontend
mkdir -p /var/www/trading/logs

# Set ownership (replace 'deploy' with your deploy user)
chown -R www-data:www-data /var/www/trading

# -----------------------------------------------------------------------------
# 7. Create Python Virtual Environment
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[7/8] Creating Python virtual environment...${NC}"
cd /var/www/trading/backend
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip

# -----------------------------------------------------------------------------
# 8. Create Systemd Services
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[8/8] Creating systemd services...${NC}"

# Trading API Service
cat > /etc/systemd/system/trading-api.service <<EOF
[Unit]
Description=Trading Bot API
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/trading/backend
Environment="PATH=/var/www/trading/backend/venv/bin"
EnvironmentFile=/var/www/trading/backend/.env
ExecStart=/var/www/trading/backend/venv/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port 8001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Trading Worker Service
cat > /etc/systemd/system/trading-worker.service <<EOF
[Unit]
Description=Trading Bot Worker
After=network.target postgresql.service redis-server.service trading-api.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/trading/backend
Environment="PATH=/var/www/trading/backend/venv/bin"
EnvironmentFile=/var/www/trading/backend/.env
ExecStart=/var/www/trading/backend/venv/bin/python -m apps.worker.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

# Enable services (don't start yet - need code deployment first)
systemctl enable trading-api
systemctl enable trading-worker

echo ""
echo -e "${GREEN}=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Add DNS record: trading.chatpsy.online → $(curl -s ifconfig.me)"
echo "2. Copy nginx config to /etc/nginx/sites-available/"
echo "3. Deploy code via GitHub Actions"
echo "4. Update /var/www/trading/backend/.env with real credentials"
echo "5. Run: sudo certbot --nginx -d trading.chatpsy.online"
echo "==========================================${NC}"
