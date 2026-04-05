.PHONY: up down seed train test lint build

# ── Docker ───────────────────────────────────────────────────────────
up:
	docker compose up --build -d
	@echo "Backend: http://localhost:8000  Frontend: http://localhost:3000"

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

# ── Local dev ────────────────────────────────────────────────────────
backend:
	cd backend && ../.venv/Scripts/python manage.py runserver

frontend:
	cd frontend && npm start

migrate:
	cd backend && ../.venv/Scripts/python manage.py migrate

migrations:
	cd backend && ../.venv/Scripts/python manage.py makemigrations

# ── Data ─────────────────────────────────────────────────────────────
seed:
	.venv/Scripts/python backend/scripts/seed_db.py
	@echo "Database seeded."

train:
	@echo "Bundled ML training has been removed."
	@echo "Plug in your own model files under backend/physio/model_bundle."

# ── Quality ──────────────────────────────────────────────────────────
test:
	cd backend && ../.venv/Scripts/python -m pytest tests/ -v --cov=. --cov-report=term-missing --cov-fail-under=60

lint:
	cd backend && ../.venv/Scripts/python -m ruff check .
	cd frontend && npm run lint

# ── Admin ────────────────────────────────────────────────────────────
superuser:
	cd backend && ../.venv/Scripts/python manage.py createsuperuser

shell:
	cd backend && ../.venv/Scripts/python manage.py shell
