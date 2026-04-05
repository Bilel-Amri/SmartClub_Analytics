# ML Integration Contract (User-Provided Model)

This project now ships without bundled ML training/inference logic.

Versioned MVP endpoints kept for integration:

- `GET /api/v1/physio/injuries/summary`
- `POST /api/v1/physio/risk/predict`

## 1) Files you need to provide

Put your exported files in:

- `backend/physio/model_bundle/`

Required:

- `manifest.json`
- `feature_schema.json`
- `class_mapping.json`
- `model.pkl` or `model.joblib`

Optional:

- `preprocessor.pkl` or `preprocessor.joblib`
- `requirements-ml.txt`
- Any tokenizer/vectorizer/encoder files your adapter needs

Templates are provided:

- `backend/physio/model_bundle/manifest.template.json`
- `backend/physio/model_bundle/feature_schema.template.json`
- `backend/physio/model_bundle/class_mapping.template.json`

## 2) Input format your model must expect

The integration contract uses this exact ordered feature list:

1. `total_distance_km` (float, required)
2. `sprints` (int, required)
3. `accelerations` (int, required)
4. `rpe` (float, required, range 1..10)
5. `sleep_quality` (float, required, range 1..10)
6. `soreness` (float, required, range 1..10)
7. `readiness` (float, required, range 1..10)
8. `minutes_played` (int, required, default 0)
9. `acwr` (float, optional, nullable)
10. `weekly_load` (float, optional, nullable)
11. `days_since_last_injury` (float, optional, nullable)
12. `fatigue` (float, optional, nullable, range 1..10)

Missing value rules:

- Required fields: reject request if missing
- Optional fields: allow null

Categorical values expected:

- No categorical input features in current default schema

## 3) Output format your model should return

Your model adapter should return a JSON-like dict with at least:

- `risk_probability`: float in [0, 1]

Recommended additional fields:

- `predicted_class`: string (for example: `low`, `medium`, `high`)
- `class_probabilities`: object mapping class name to probability
- `top_factors`: array of objects: `{ "feature": string, "value": number }`
- `model_version`: string

Backend will expose a response used by frontend that includes:

- `risk_probability`
- `risk_pct`
- `risk_band`
- `confidence_band`
- `recommended_action`
- `monitoring_note`
- `flag_for_physio_review`
- `top_factor`
- `shap_factors` (mapped from `top_factors`)

## 4) Minimal integration files that remain

Backend:

- `backend/physio/views.py` (API shell + adapter hook)
- `backend/physio/urls.py` (existing endpoint routing)
- `backend/physio/model_bundle/README.md`
- `backend/physio/model_bundle/*.template.json`

Frontend (unchanged integration points):

- `frontend/src/components/PhysioAI.js`

## 5) Which file to replace with your own model connection

Implement your loading/prediction logic in:

- `backend/physio/views.py` inside `_predict_with_user_model`

Minimal code area:

- `backend/physio/views.py`
	- `_predict_with_user_model(features, horizon)`
	- optional schema override via `backend/physio/model_bundle/feature_schema.json`

And add your exported artifacts in:

- `backend/physio/model_bundle/`

## 6) Final artifact folder for your exports

Use exactly this folder:

- `backend/physio/model_bundle/`
