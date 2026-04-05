# PhysioAI — Decision Logic Reference

## Risk Band Classification

Computed on every call to `InjuryRiskView` and `GlobalRiskView`.

| Band | Probability threshold | Colour |
|---|---|---|
| `low` | `prob < 0.25` | Green `#22c55e` |
| `medium` | `0.25 ≤ prob < 0.55` | Amber `#f59e0b` |
| `high` | `prob ≥ 0.55` | Red `#ef4444` |

Implementation (`views.py → _compute_decision_support`):
```python
risk_band = "low"
if prob >= 0.55:
    risk_band = "high"
elif prob >= 0.25:
    risk_band = "medium"
```

---

## Data Quality Score

Measures how much usable training signal exists for a given player.

```python
def _assess_data_quality(recent_loads):
    """
    Returns (sufficient_history: bool, data_quality_score: float 0–1)
    """
    if len(recent_loads) < 5:
        return False, len(recent_loads) / 5.0

    key_fields = ["total_distance_km", "rpe", "sleep_quality", "sprints", "accelerations"]
    non_null = sum(
        1 for load in recent_loads for f in key_fields
        if getattr(load, f, None) is not None
    )
    total = len(recent_loads) * len(key_fields)
    score = non_null / total if total > 0 else 0.0
    return score >= 0.40, round(score, 3)
```

**Threshold:** `score ≥ 0.40` AND `len(recent_loads) ≥ 5` → `sufficient_history = True`

---

## Confidence Band

| Band | Condition |
|---|---|
| `low` | `not sufficient_history` OR `data_quality_score < 0.40` |
| `high` | `sufficient_history` AND `data_quality_score ≥ 0.75` |
| `medium` | everything else |

```python
if not sufficient_history or data_quality_score < 0.40:
    confidence_band = "low"
elif data_quality_score >= 0.75:
    confidence_band = "high"
else:
    confidence_band = "medium"
```

---

## Recommended Action

Generated as human-readable text based on risk + confidence combination.

| Risk | Confidence | Action |
|---|---|---|
| high | high | Immediate physio assessment. Consider load reduction or rest day. Monitor closely over next 48h. |
| high | medium | High risk indicated. Recommend physio review within 24h and load adjustment. |
| high | low | High risk flagged but data quality is limited. Clinical assessment recommended. |
| medium | high | Elevated risk. Maintain current load, monitor wellness markers daily. |
| medium | medium/low | Monitor player. Consider reducing intensity if subjective wellness declines. |
| low | * | Low risk. Continue standard training protocol. Routine monitoring. |

---

## Flag for Physio Review

`flag_for_physio_review = True` when `risk_band == "high"` AND `sufficient_history == True`.

Rationale: Do not auto-flag low-confidence high-risk readings — data quality is insufficient to warrant mandatory clinical action.

---

## Monitoring Note

Appended when `confidence_band == "low"`:
> "Prediction confidence is low due to limited or incomplete load data. Increase data collection to improve model reliability."

---

## Recurrence Detection (Returning Players)

A returning player is marked `recurrence_flag = True` when:
- They have ≥2 injury records of the **same injury type** in history

```python
recurrence_flag = injuries.filter(
    player=injury.player,
    injury_type=injury.injury_type
).count() >= 2
```

---

## Load Spike Detection (Squad Overview)

`load_spike = True` for a player when their most recent load record has:
- `rpe ≥ 8.0` (high perceived exertion)
- OR `total_distance_km > last_7d_avg * 1.3` (30% above rolling average)

---

## Model Versioning

Model version string is constructed at load time:
```
physio_global_v{major}.{minor}_{horizon}d
```

Example: `physio_global_v1.0_7d`

The version is stored in every `InjuryRiskPrediction` row for full auditability.
