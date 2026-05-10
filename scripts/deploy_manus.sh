#!/bin/bash
set -euo pipefail

REPO=/home/ubuntu/ncore-genesis-vfinal
SOVEREIGN=/home/ubuntu/sovereign

# 1. Install system deps
sudo apt-get update
sudo apt-get install -y nginx python3-pip pnpm nodejs

# 2. Install Python deps
pip3 install fastapi uvicorn httpx playwright
playwright install chromium

# 3. Pull latest code
cd "$REPO" && git pull origin main

# 4. Build frontend
cd "$REPO/apps/mission-control"
pnpm install
pnpm build

# 5. Deploy static files
sudo rm -rf /var/www/mission-control
sudo mkdir -p /var/www/mission-control
sudo cp -r "$REPO/apps/mission-control/dist/"* /var/www/mission-control/
sudo chown -R www-data:www-data /var/www/mission-control

# 6. Deploy nginx config
sudo cp "$REPO/sovereign/nginx.conf" /etc/nginx/sites-available/mission-control
sudo ln -sf /etc/nginx/sites-available/mission-control /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# 7. Install systemd services
sudo cp "$REPO/scripts/manus-mission-control.service" /etc/systemd/system/
sudo cp "$REPO/scripts/bifrost.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bifrost
sudo systemctl enable --now manus-mission-control

# 8. Start docker compose services
cd "$SOVEREIGN" && docker compose up -d

echo "✅ Manus Mission Control deployed"
echo "Dashboard: http://localhost"
echo "API: http://localhost/api/"
