# ML Training Assets

This folder stores training notebooks and optional local artifact outputs.

## Notebooks

- `notebooks/injury_risk_model.ipynb`
  - Source: original `injury.ipynb`
  - Task: injury risk classification (`is_risk`, binary)
  - Model family: CatBoostClassifier
  - Typical exported files:
    - `model_risk.pkl`
    - `risk_schema.json`

- `notebooks/absence_days_model.ipynb`
  - Source: original `missing-days.ipynb`
  - Task: injury absence duration regression (days)
  - Model family: CatBoostRegressor
  - Typical exported files:
    - `model_absence_days.pkl`
    - `absence_days_schema.json`

## Production Runtime Mapping

The backend serves predictions from files in:

- `backend/physio/model_bundle/`

Expected runtime files include:

- `model_risk.pkl`
- `risk_schema.json`
- `model_absence_days.pkl`
- `absence_days_schema.json`

If you retrain notebooks, copy validated outputs into `backend/physio/model_bundle/`.

## Artifact Policy

- Keep heavy experimental artifacts in `ml/artifacts/` locally.
- Do not commit large temporary bundles unless intentionally versioning a release model package.
