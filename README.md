<div align="center">

<img src="https://img.shields.io/badge/SmartClub-Analytics-1a1a2e?style=for-the-badge&logo=soccer&logoColor=white" alt="SmartClub Analytics" width="400"/>

# ⚽ SmartClub Analytics

**An AI-powered football club management platform** — injury prediction, nutrition planning, intelligent scouting, and real-time monitoring, all in one place.

[![Django](https://img.shields.io/badge/Django-4.2-092E20?style=flat-square&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://reactjs.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![CatBoost](https://img.shields.io/badge/CatBoost-ML-yellow?style=flat-square)](https://catboost.ai/)
[![JWT](https://img.shields.io/badge/Auth-JWT-000000?style=flat-square&logo=jsonwebtokens&logoColor=white)](https://jwt.io/)
[![License](https://img.shields.io/badge/License-All%20Rights%20Reserved-red?style=flat-square)](#license)

---

> Built on real sports science datasets: **SoccerMon**, **StatsBomb Open Data**, and **USDA FoodData Central**.

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [ML Models](#-ml-models)
- [API Reference](#-api-reference)
- [User Roles & RBAC](#-user-roles--rbac)
- [Quickstart](#-quickstart)
- [Environment Variables](#-environment-variables)
- [Data & Seeding](#-data--seeding)
- [Running Tests](#-running-tests)
- [Project Structure](#-project-structure)
- [Contributing](#-contributing)

---

## 🌟 Overview

**SmartClub Analytics** is a full-stack, AI-driven sports management platform designed for professional football clubs. It unifies injury prevention, nutrition management, player scouting, and operational monitoring under a single authenticated dashboard.

The platform is built on three real-world sports datasets and uses production-grade machine learning models trained on actual injury and wellness data from European football.

---

## ✨ Features

| Module | Highlights |
|--------|-----------|
| 🔐 **Auth & RBAC** | JWT-based login with 5 role types; custom claims include role + full name |
| 📊 **Dashboard** | Live squad health summary, injury trends, training load KPIs, xG leaderboards |
| 🏥 **PhysioAI v2** | ML risk scoring (CatBoost, AUC 0.896), absence prediction, what-if simulator, AI narrative explanations |
| 🥗 **NutriAI** | Personalized meal plans, macro tracking, USDA food database (436 foods), supplement compliance |
| 🏟️ **ScoutAI** | Player profiles, contract management, StatsBomb per-player stats |
| 💬 **Chatbot** | Rule-based ORM chatbot with 14 intents and smart player name resolution |
| 🤖 **Chat LLM** | LLM-powered agent with SSE streaming, multi-language support (EN/FR/AR/TN) |
| 📈 **Monitoring** | Real-time API traffic, latency percentiles (p50/p95/p99), system resource graphs |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    React 18 Frontend :3000                   │
│  Dashboard · PhysioAI · NutriAI · Chatbot · Monitoring UI   │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP / JSON / SSE
┌────────────────────────▼────────────────────────────────────┐
│                  Django REST API :8000                        │
│                                                              │
│  /api/auth/          /api/v2/physio/     /api/nutri/         │
│  /api/scout/         /api/chat/          /api/chat-llm/      │
│  /api/dashboard/     /api/monitoring/                        │
└──────────┬──────────────────────┬───────────────────────────┘
           │                      │
    ┌──────▼───────┐    ┌─────────▼──────────────┐
    │  PostgreSQL   │    │  model_bundle/          │
    │  (or SQLite)  │    │  ├ model_risk.pkl       │
    └──────────────┘    │  └ model_absence_days.pkl│
                        └────────────────────────┘
```

---

## 🛠️ Tech Stack

**Backend**
- **Django 4.2** + **Django REST Framework**
- **SimpleJWT** for authentication
- **CatBoost** (Classifier + Regressor) for injury ML
- **psutil** for system monitoring
- **Groq / OpenAI / OpenRouter** for LLM narratives

**Frontend**
- **React 18** (Webpack)
- **Recharts** for data visualization
- JWT-aware API client

**Data**
- **SoccerMon** — 50 players, 731 days, 162 injuries (wellness & load tracking)
- **StatsBomb Open Data** — La Liga 2020/21 player stats
- **USDA FoodData Central** — 436 Foundation Foods

---

## 🤖 ML Models

Two production-grade models power the PhysioAI v2 module:

### 1. Injury Risk Classifier (`model_risk.pkl`)
> Notebook: [`ml/notebooks/injury_risk_model.ipynb`](ml/notebooks/injury_risk_model.ipynb)

| Property | Detail |
|----------|--------|
| Algorithm | `CatBoostClassifier` |
| Dataset | SoccerMon (19 wellness/load files, 50 players) |
| Target | Binary — `is_risk`: 1 if within 7 days before an injury |
| Best AUC | **0.896** |
| Features | Fatigue, sleep quality, ACWR, soreness, readiness, and more |
| Output | Risk probability + band (Low / Medium / High) |

### 2. Absence Duration Regressor (`model_absence_days.pkl`)
> Notebook: [`ml/notebooks/absence_days_model.ipynb`](ml/notebooks/absence_days_model.ipynb)

| Property | Detail |
|----------|--------|
| Algorithm | `CatBoostRegressor` |
| Dataset | European Football Injuries 2020–2025 (~15,600 records) |
| Target | Days absent (capped at 180, log1p-transformed for stability) |
| MAE | ~21 days on validation set |
| Features | Injury type/group, club, league, player age, position, season phase |
| Output | Predicted days absent + severity bucket (0–7 / 8–21 / 22–42 / 43+) |

Both model artifacts live in `backend/physio/model_bundle/` and are loaded by `prediction_service.py` at inference time.

---

## 🔌 API Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/token/` | Obtain JWT access + refresh tokens |
| `POST` | `/api/auth/token/refresh/` | Refresh access token |
| `POST` | `/api/auth/register/` | Register new user |
| `GET` | `/api/auth/me/` | Current user info |

### PhysioAI v2 (active routes)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v2/physio/squad/daily-risk` | ML risk score for all players today |
| `POST` | `/api/v2/physio/simulator/assess` | What-if risk simulation |
| `POST` | `/api/v2/physio/absence/predict` | Predict absence days |
| `POST` | `/api/v2/physio/ai/explain` | LLM clinical narrative explanation |
| `GET` | `/api/v2/physio/ml/health` | Model bundle health check |
| `GET` | `/api/v2/physio/players/profiles` | Player profiles for PhysioAI UI |

### NutriAI
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/nutri/foods/` | Food database |
| `POST` | `/api/nutri/generate-plan/` | Auto-generate meal plan (rule-based) |
| `POST` | `/api/nutri/meal-calc/` | Compute macros for custom food list |
| `GET/POST` | `/api/nutri/meal-logs/` | Log food entries |
| `GET` | `/api/nutri/meal-logs/totals/` | Actual vs target macro totals |
| `GET/POST` | `/api/nutri/supplements/` | Supplement tracker |

### Scout
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/scout/players/` | List / create players |
| `GET/PUT/DELETE` | `/api/scout/players/{id}/` | Player detail |
| `GET/POST` | `/api/scout/contracts/` | Contract management |

### Chat & LLM
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat/` | Rule-based chatbot (14 intents) |
| `POST` | `/api/chat-llm/` | LLM agent (JSON response) |
| `POST` | `/api/chat-llm/stream/` | LLM agent (SSE streaming) |

### Dashboard & Monitoring
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/dashboard/summary/` | Squad KPIs, injury trends, xG leaders |
| `GET` | `/api/monitoring/metrics/` | API traffic, latency, resource time series |

---

## 👥 User Roles & RBAC

The system enforces role-based access at the API level.

| Role | Access |
|------|--------|
| `admin` | Full system access |
| `coach` | Dashboard, squad overview, training loads |
| `physio` | PhysioAI module, injury logs, wellness data |
| `nutritionist` | NutriAI module, meal plans, supplements |
| `scout` | Scout module, player profiles, contracts |

JWT tokens carry custom claims: `user_id`, `role`, `full_name`.

---

## 🚀 Quickstart

### Prerequisites
- Python 3.10+
- Node.js 18+
- (Optional) PostgreSQL — SQLite is used by default in dev

### 1. Clone the repo
```bash
git clone https://github.com/Bilel-Amri/SmartClub_Analytics.git
cd SmartClub_Analytics
```

### 2. Backend setup
```bash
# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and set at minimum: DJANGO_SECRET_KEY, SOCCERMON_PATH, FOODDATA_PATH

# Migrate and seed
cd backend
python manage.py migrate
python scripts/seed_db.py              # players, contracts, injuries
python manage.py import_fooddata       # USDA foods (optional)
python manage.py seed_statsbomb        # StatsBomb stats (optional)

# Start the server
python manage.py runserver 127.0.0.1:8000
```

Default superuser credentials after seeding: **admin / admin123** *(change in production)*

### 3. Frontend setup
```bash
cd frontend
npm install
npm start           # starts at http://localhost:3000
```

### 4. Docker (alternative)
```bash
docker-compose up --build
```

---

## ⚙️ Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# Required
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
SOCCERMON_PATH=/path/to/soccermon/csv/folder
FOODDATA_PATH=/path/to/usda/fooddata/folder

# Optional — Switch to PostgreSQL
USE_POSTGRES=False
DATABASE_URL=postgres://user:pass@localhost:5432/smartclub

# Optional — LLM provider (for PhysioAI explanations and Chat LLM)
GROQ_API_KEY=
OPENAI_API_KEY=
OPENROUTER_API_KEY=
```

---

## 🗄️ Data & Seeding

| Command | Description |
|---------|-------------|
| `python manage.py migrate` | Initialize database schema |
| `python scripts/seed_db.py` | Seed 18 players, contracts, injuries, loads |
| `python manage.py import_fooddata` | Import USDA FoodData Central (needs `FOODDATA_PATH`) |
| `python manage.py seed_statsbomb` | Import StatsBomb La Liga stats (needs internet) |

> ⚠️ **Note:** The local SQLite database is not committed to the repo. Run `migrate` before your first server start.

---

## 🧪 Running Tests

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

- **52 tests** across all modules
- **43% coverage** against a 35% configured threshold
- Django system check: `python manage.py check`

---

## 📂 Project Structure

```
SmartClub_Analytics/
├── backend/
│   ├── smartclub/              # Django settings & root URL config
│   ├── users/                  # Custom user model, JWT, RBAC
│   ├── scout/                  # Player profiles, contracts (data layer)
│   ├── physio/                 # PhysioAI v2: injuries, loads, ML risk
│   │   ├── urls_v2.py          # Active routes — /api/v2/physio/
│   │   ├── views_v2.py         # v2 view handlers
│   │   ├── prediction_service.py
│   │   ├── vulnerability_formula.py
│   │   ├── groq_layer.py       # LLM narrative generation
│   │   └── model_bundle/       # CatBoost model artifacts (gitignored)
│   ├── nutri/                  # Food DB, meal plans, supplements
│   ├── chat/                   # Rule-based chatbot (14 intents)
│   ├── chat_llm/               # LLM agent with SSE streaming
│   ├── dashboard/              # Summary API
│   ├── monitoring/             # Request metrics + resource monitoring
│   ├── scripts/seed_db.py      # CSV data seeder
│   ├── tests/                  # pytest suite (52 tests)
│   ├── requirements.txt        # Production dependencies
│   └── requirements-dev.txt    # Dev/test dependencies
│
├── frontend/
│   ├── src/
│   │   ├── App.js              # Root app, routing, Dashboard
│   │   ├── auth.js             # JWT helpers
│   │   └── components/         # PhysioAIv2, NutriAI, Chatbot, Monitoring
│   └── package.json
│
├── ml/
│   ├── notebooks/
│   │   ├── injury_risk_model.ipynb     # CatBoostClassifier (AUC 0.896)
│   │   └── absence_days_model.ipynb    # CatBoostRegressor
│   └── README.md               # Training ↔ production artifact mapping
│
├── seed/                       # CSV seed files
├── docs/                       # Architecture specs, RBAC matrix
├── .github/workflows/ci.yml    # CI: tests + build
├── .gitignore
├── CONTRIBUTING.md
├── LICENSE
├── docker-compose.yml
└── README.md
```

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on setting up your dev environment, running tests, and submitting pull requests.

---

## 📄 License

© 2025 Bilel Amri. All rights reserved.

This project is proprietary software. Unauthorized copying, distribution, or modification is not permitted.

---

<div align="center">

Built with ❤️ for professional football intelligence.

**[⬆ Back to top](#-smartclub-analytics)**

</div>
