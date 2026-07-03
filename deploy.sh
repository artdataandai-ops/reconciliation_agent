#!/bin/bash
set -e

# ============================================
# Reconciliation Agent Docker Deploy Script
# Runs on the server after git push.
# Usage: bash /var/www/apps/reconciliation-agent/deploy.sh
# ============================================

DEPLOY_DIR="/var/www/apps/reconciliation_agent"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.yml"

echo "=========================================="
echo "Reconciliation Agent Deploy - $(date)"
echo "=========================================="

cd "$DEPLOY_DIR"

# [1/4] Pull latest code
echo "[1/4] Pulling latest code..."
git pull origin main

# [2/4] Build and (re)start containers
echo "[2/4] Building and restarting containers..."
docker compose -f "$COMPOSE_FILE" up -d --build

# [3/4] Wait for the backend to come up
echo "[3/4] Waiting for backend (8s)..."
sleep 8

# [4/4] Reload bundled nginx (picks up deploy/nginx/reconciliation.conf changes)
echo "[4/4] Reloading bundled nginx..."
docker exec reconciliation-nginx nginx -t && docker exec reconciliation-nginx nginx -s reload \
  || echo "Warning: nginx reload skipped (first deploy?)"

# Status
echo ""
echo "Container status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "reconciliation|NAMES"

echo "=========================================="
echo "Deploy finished at $(date)"
echo "Public URL (via edge nginx): https://ai.arttechgroup.com:7777/reconciliation-agent/api"
echo "=========================================="
