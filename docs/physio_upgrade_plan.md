# PhysioAI — Club-Pilot Upgrade Plan

## Overview

Transform SmartClub Analytics PhysioAI module from MVP to a club-pilot-ready premium platform with decision-support, squad monitoring, RBAC, and ML productization.

---

## Phase 1 — Decision Support Backend ✅

**Goal:** Enrich every injury-risk API response with actionable clinical guidance.

### Changes
- `backend/physio/models.py` — Added 9 fields to `InjuryRiskPrediction`:
  - `risk_band` (low / medium / high)
  - `confidence_band` (low / medium / high)
  - `recommended_action` (text)
  - `monitoring_note` (text)
  - `flag_for_physio_review` (bool)
  - `sufficient_history` (bool)
  - `data_quality_score` (float 0–1)
  - `top_factor` (char — top SHAP feature name)
  - `model_version` (char)
- Added `FlagAcknowledgment` model: tracks physio acknowledgments of high-risk alerts
- Added `AuditLog` model: immutable event log for GDPR and clinical governance

### New endpoints (all prefixed `/api/physio/`)
| Endpoint | Method | Description |
|---|---|---|
| `overview/today` | GET | Squad-level KPI summary + per-player risk |
| `flagged` | GET | Players flagged for physio review |
| `returning` | GET | Players returning ≤14 days from injury |
| `acknowledge/<player_id>/` | POST | Acknowledge a high-risk flag |
| `player/<player_id>/predictions/` | GET | Prediction history for one player |
| `model-metadata` | GET | Model version, metrics, feature list |
| `audit-log/` | GET | GDPR-ready audit trail |
| `import/injuries/` | POST | Bulk CSV import (admin only) |
| `import/loads/` | POST | Bulk CSV import (admin only) |
| `global/squad-overview` | GET | Global (SoccerMon) squad risk table |

### Migration
- `0004_injuryriskprediction_confidence_band_...` applied

---

## Phase 2 — Premium Frontend UI ✅

**Goal:** Replace MVP PhysioAI with professional, clinic-grade interface.

### New components added to `PhysioAI.js`
- `RiskBadge` — colour-coded band label
- `ConfidenceBadge` — confidence level indicator
- `KpiCard` — headline metric tile
- `Skeleton` — shimmer loading placeholder
- `EmptyState` — icon + text empty state
- `Flash` — ephemeral notification toast
- `ShapFactors` — bar-chart SHAP driver list
- `RiskGauge` — animated probability bar
- `DecisionCard` — full recommended action + monitoring note card
- `SquadRow` — clickable squad table row with risk bar

### Panel structure
- **GlobalPanel** tabs: Squad Overview | Individual Risk
- **ClubPanel** tabs: Squad | Risk | Flagged | Injuries | Loads | History
- Data-source toggle: 🌍 SoccerMon or 🏠 Club Seed

---

## Phase 3 — RBAC Hardening ✅

**Goal:** Enforce least-privilege access across all physio endpoints.

### `backend/physio/permissions.py`
| Class | Allowed |
|---|---|
| `IsAdminOrPhysio` | admin, physio — full CRUD |
| `IsCoachOrAbove` | admin, physio, coach — read |
| `IsPhysioReadOnly` | POST: physio+admin; GET: coach+ |
| `IsAdminOnly` | admin — CSV import, audit log |

See `docs/rbac_matrix.md` for per-endpoint matrix.

---

## Phase 4 — ML Productization ✅

**Goal:** Persist predictions, expose model metadata, track history.

### Changes
- `InjuryRiskView` and `GlobalRiskView` now persist each prediction to `InjuryRiskPrediction`
- `PredictionHistoryView` returns last N predictions per player + trend data
- `ModelMetadataView` exposes model version, training date, feature names, test metrics
- SHAP top factor persisted as `top_factor` field

---

## Phase 5 — Squad Support ✅

**Goal:** Enable physio to manage a full squad, not just individual players.

### New views
- `SquadOverviewTodayView` — latest prediction per player + load spike flag
- `FlaggedPlayersView` — all unresolved `flag_for_physio_review=True` predictions
- `AcknowledgeFlagView` — POST to create `FlagAcknowledgment` record
- `ReturningPlayersView` — injuries with expected_return ≤14 days + recurrence detection
- `GlobalSquadOverviewView` — same as club but across SoccerMon global players

---

## Phase 6 — Documentation ✅

This file and siblings:
- `docs/physio_upgrade_plan.md` — this document
- `docs/physio_decision_logic.md` — risk/confidence algorithms
- `docs/ui_professionalization.md` — UI component guide
- `docs/rbac_matrix.md` — permission matrix

---

## Deployment Checklist

1. `python backend/manage.py migrate` — apply migration 0004
2. `python backend/manage.py check` — verify 0 issues
3. Restart Django server
4. Rebuild frontend: `npm run build` inside `frontend/`
5. Log in as `admin/admin123` and verify PhysioAI data-source toggle
