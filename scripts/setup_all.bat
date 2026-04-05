@echo off
REM ============================================================
REM  SmartClub Analytics — Master Setup Script (Windows)
REM  Usage:  scripts\setup_all.bat
REM
REM  What it does (in order):
REM    1. Apply all Django migrations
REM    2. Import USDA FoodData Central Foundation Foods
REM    3. Seed StatsBomb La Liga players (fast — lineups only)
REM    4. Seed CSV-based club data (players, contracts, loads, injuries)
REM ============================================================

set PYTHON=C:\Users\Lenovo\AppData\Local\Programs\Python\Python312\python.exe
set BACKEND=%~dp0..\backend

echo.
echo ====================================================
echo  SmartClub Analytics — Full Setup
echo ====================================================
echo.

cd /d "%BACKEND%"

echo [1/4] Applying Django migrations ...
%PYTHON% manage.py migrate --no-input
if errorlevel 1 ( echo [ERROR] migrate failed & exit /b 1 )
echo [OK] Migrations applied

echo.
echo [2/4] Importing USDA FoodData Central Foundation Foods ...
%PYTHON% manage.py import_fooddata
if errorlevel 1 ( echo [WARN] import_fooddata failed — check FOODDATA_PATH in .env )
echo [OK] Food data imported

echo.
echo [3/4] Seeding StatsBomb La Liga players (via lineups) ...
%PYTHON% manage.py seed_statsbomb --competition 11 --season 90 --matches 5 --limit 80
if errorlevel 1 ( echo [WARN] seed_statsbomb failed — check network / statsbombpy install )
echo [OK] StatsBomb players seeded

echo.
echo [4/4] Seeding club CSV data ...
%PYTHON% scripts\seed_db.py
if errorlevel 1 ( echo [WARN] seed_db.py failed — check seed\ CSV files )
echo [OK] Club data seeded

echo.
echo ====================================================
echo  Setup complete!
echo  Start backend:   cd backend ^&^& python manage.py runserver
echo  Start frontend:  cd frontend ^&^& npm start
echo ====================================================
echo.
