# PhysioAI v2 Specification

## Section 1 - Global architecture
- Layer 1 (ML model): Computes risk and absence severity only.
- Layer 2 (Similarity engine): Retrieves nearest historical evidence only.
- Layer 3 (Groq AI): Explains result in human text only when user clicks explain.
- Rule: No layer overlaps responsibilities.

## Section 2 - Database schema (6 PostgreSQL tables)
1. physio_physicalcase: historical injury cases for k-NN retrieval.
2. physio_physiosquadsnapshot: daily per-player squad risk snapshots.
3. physio_physiorisksimulationrun: simulation assessments for arbitrary profiles.
4. physio_physioabsencepredictionrun: absence estimation records.
5. physio_physiosimilaritymatch: linked similarity matches with rank and match_pct.
6. physio_physioaiexplanation: explanation logs, provider, fallback flag.

## Section 3 - Machine learning engine
- Model 1: vulnerability formula (deterministic, points by factor).
- Model 2a (Risk): RandomForestClassifier loaded from model_risk.pkl via physio.prediction_service singleton.
- Model 2b (Absence): CatBoostRegressor loaded from model_absence_days.pkl via physio.prediction_service singleton.
- AUC reference: 0.656 (when schema value absent, fallback constant 0.656).
- Artifacts expected in model bundle:
  - model_risk.pkl
  - risk_schema.json
  - model_absence_days.pkl
  - absence_days_schema.json

## Section 4 - Similarity engine
- Risk simulation vector: age, previous injuries, injuries_last_2_seasons, recurrence, load band, days_since_last_intense.
- Absence vector: age, previous_same_zone, recurrence, load band, absence anchor days.
- Method: Euclidean k-NN over historical cases (top-3 cards).
- UI output: count, aggregate stats, profile summary, 3 ranked cards with match percentages.

## Section 5 - API endpoints
### PhysioAI v2
- GET /api/v2/physio/squad/daily-risk
- POST /api/v2/physio/simulator/assess
- POST /api/v2/physio/absence/predict
- POST /api/v2/physio/ai/explain
- GET /api/v2/physio/ml/health
- POST /api/v2/physio/similarity/seed

### NutriAI existing endpoints
- GET/POST /api/nutri/foods/
- GET/POST /api/nutri/plans/
- POST /api/nutri/generate-plan/
- POST /api/nutri/meal-calc/
- GET/POST /api/nutri/meal-logs/
- GET /api/nutri/meal-logs/totals/
- GET/POST /api/nutri/supplements/

## Section 6 - Groq AI layer
- System prompt: clinical, concise, no hallucinations, plain text.
- Prompt templates:
  - squad_daily_risk
  - player_risk_simulator
  - absence_prediction
- Called only via POST /api/v2/physio/ai/explain (user action).
- Fallback: deterministic local explanation if GROQ_API_KEY missing or API call fails.

## Section 7 - React frontend three-tab interface
- Tab 1: Squad daily risk
  - KPI strip + grouped lists
  - First high-risk card expanded by default
  - Explain button per card
- Tab 2: Player risk simulator
  - Profile form left, output right
  - Score ring, drivers, decisions, similar profiles, AI explanation
- Tab 3: Absence prediction
  - Injury event form left, prediction + case matching right
  - Explain button for user-triggered Groq text

## Section 8 - Scoring formula
- See backend/physio/vulnerability_formula.py
- Function: compute_vulnerability_score(...)
- Output: risk_score, risk_band, breakdown, top_drivers

## Section 9 - Colour system
- --physio-bg: #030b18
- --physio-card: #0b1730
- --physio-card-2: #121d3a
- --physio-border: #1f335f
- --physio-text: #d9e8ff
- --physio-muted: #6f8fbd
- --physio-risk-high: #ff3a6e
- --physio-risk-medium: #f4b322
- --physio-risk-low: #1fe88f
- --physio-accent-cyan: #00d4ff
- --physio-accent-violet: #8c63ff

## Sections 10-11 - Project structure
### Django
- physio/models.py (v2 tables)
- physio/views_v2.py (three functions + ai + health)
- physio/urls_v2.py
- physio/vulnerability_formula.py
- physio/similarity_service.py
- physio/groq_layer.py

### React
- src/components/PhysioAIv2.js
- src/App.js imports PhysioAIv2 for Physio module entry

## Section 12 - Rules
- Never auto-call Groq on page load.
- Never show synthetic certainty language.
- Never mix model output with explanation generation logic.
- UI rules:
  - graceful fallback messaging if AI unavailable
  - one-click explain action only
  - preserve deterministic outputs without AI
- Data flow:
  - Squad risk: input player state -> formula/model -> similarity optional -> user explain
  - Simulator: profile input -> formula -> similarity -> user explain
  - Absence: injury event -> severity model -> similarity -> user explain

## Section 13 - Jury sentences
1. We separate prediction, evidence retrieval, and explanation into three independent layers to keep decisions auditable.
2. The AI assistant never predicts risk; it only explains model and similarity outputs on explicit user request.
3. Similarity cards are retrieved with k-NN from historical cases to provide transparent precedent, not black-box narrative.
4. Our absence model is artifact-driven and benchmarked at AUC 0.656 in the exported validation schema.
5. The interface is intentionally decision-first: clear risk bands, immediate actions, and controlled escalation pathways.
