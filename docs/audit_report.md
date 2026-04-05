# Phase 0: Forensic Audit Report

## 1. Mocked & Hardcoded Elements
The current application relies heavily on synthetic data and hardcoded logic to simulate a working product.

### Frontend (React)
- **Dashboard (`App.js`)**: The "Executive Snapshot" charts (`mockBarData`, `mockPieData`, `mockLineData`) are entirely hardcoded.
- **PhysioAI (`PhysioAI.js`)**: The `GlobalPanel` uses hardcoded `<optgroup>` and `<option>` tags for "Team A" and "Team B" players instead of fetching the roster dynamically.
- **ScoutAI (`ScoutAI.js`)**: The UI lacks dynamic filters for positions, leagues, or age ranges, relying on whatever the backend returns.

### Backend (Django)
- **Scouting Logic (`scout/views.py`)**: The `score_player` function uses hardcoded `DEFAULT_STATS` and `ROLE_WEIGHTS` to calculate a player's score. It does not use real match data.
- **Physio Logic (`physio/views.py`)**: The `_rule_based_risk` function uses hardcoded thresholds (e.g., `load > 2000`, `sleep < 5`) to determine injury risk. The ML model (`physio_risk_model.pkl`) is a basic XGBoost model trained on synthetic data.
- **Database Seeding (`scripts/seed_db.py`)**: The `seed_match_stats` function generates fake match statistics using `random.uniform` and `random.randint`.

## 2. API-Driven Elements
The application has a functional REST API, but it primarily serves the synthetic data.

- **Endpoints**: The frontend successfully communicates with the backend via standard DRF endpoints (`/api/scout/players/`, `/api/physio/players/`, `/api/nutri/foods/`, etc.).
- **CRUD Operations**: Basic Create, Read, Update, and Delete operations are functional for players, injuries, training loads, and nutrition logs.
- **AI Endpoints**: The `/api/chat/ask/` endpoint is functional but relies on a basic OpenAI integration without RAG (Retrieval-Augmented Generation) or context awareness.

## 3. SQLite-Dependent Elements
The application is currently tightly coupled to SQLite for local development.

- **Configuration (`smartclub/settings.py`)**: The default database engine is `django.db.backends.sqlite3`. While a `USE_POSTGRES` toggle exists, it is not currently active.
- **Migrations**: The existing migration files (`migrations/`) were generated against SQLite. Moving to PostgreSQL will require a fresh migration strategy to avoid compatibility issues.
- **Concurrency**: SQLite is not suitable for a production environment with multiple concurrent users (e.g., coaches, physios, and scouts accessing the system simultaneously).

## 4. Security & Authentication
The application currently lacks robust security measures.

- **Authentication**: JWT settings are present in `settings.py`, but the default permission class is set to `AllowAny`, meaning all endpoints are publicly accessible.
- **Role-Based Access Control (RBAC)**: There is no mechanism to restrict access based on user roles (e.g., preventing a scout from viewing sensitive medical data).

## 5. Machine Learning & Data Science
The current ML implementation is a placeholder.

- **PhysioAI**: The existing model is trained on synthetic data and lacks real-world predictive power. It needs to be replaced with a model trained on the SoccerMon dataset, incorporating proper time-based splitting and SHAP explainability.
- **ScoutAI**: Currently relies on hardcoded weights. It needs to be upgraded to use StatsBomb Open Data for realistic player evaluation.

---

## Next Steps
To proceed with Phase 1 (Foundation & Security) and Phase 2 (Data Science & ML), we need to integrate the real datasets.
