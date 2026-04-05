#!/usr/bin/env bash
# ============================================================
#  SmartClub Analytics — Master Setup Script (Linux / macOS)
#  Usage:  bash scripts/setup_all.sh
#
#  What it does (in order):
#    1. Apply all Django migrations
#    2. Import USDA FoodData Central Foundation Foods
#    3. Seed StatsBomb La Liga players (fast — lineups only)
#    4. Seed CSV-based club data (players, contracts, loads, injuries)
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$SCRIPT_DIR/../backend"
ML="$SCRIPT_DIR/../ml"
PYTHON="${PYTHON:-python}"  # override with PYTHON=python3 bash scripts/setup_all.sh

echo ""
echo "===================================================="
echo " SmartClub Analytics — Full Setup"
echo "===================================================="
echo ""

cd "$BACKEND"

echo "[1/4] Applying Django migrations ..."
$PYTHON manage.py migrate --no-input
echo "[OK] Migrations applied"

echo ""
echo "[2/4] Importing USDA FoodData Central Foundation Foods ..."
$PYTHON manage.py import_fooddata || echo "[WARN] import_fooddata failed — check FOODDATA_PATH in .env"
echo "[OK] Food data imported"

echo ""
echo "[3/4] Seeding StatsBomb La Liga players (via lineups) ..."
$PYTHON manage.py seed_statsbomb --competition 11 --season 90 --matches 5 --limit 80 || echo "[WARN] seed_statsbomb failed"
echo "[OK] StatsBomb players seeded"

echo ""
echo "[4/4] Seeding club CSV data ..."
$PYTHON scripts/seed_db.py || echo "[WARN] seed_db.py failed — check seed/ CSV files"
echo "[OK] Club data seeded"

echo ""
echo "===================================================="
echo " Setup complete!"
echo " Start backend:   cd backend && python manage.py runserver"
echo " Start frontend:  cd frontend && npm start"
echo " Or via Docker:   docker compose up --build"
echo "===================================================="
echo ""
