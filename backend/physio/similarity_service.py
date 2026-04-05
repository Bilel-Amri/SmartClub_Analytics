from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

import numpy as np

from .models import PhysioHistoricalCase


@dataclass
class SimilarityResult:
    case_id: int
    rank: int
    distance: float
    match_pct: float
    summary: str
    payload: Dict


def _load_band_num(v: str) -> float:
    m = {"low": 1.0, "medium": 2.0, "high": 3.0}
    return m.get((v or "medium").lower(), 2.0)


def _injury_vector(case: PhysioHistoricalCase) -> np.ndarray:
    return np.array(
        [
            float(case.age),
            float(case.previous_injuries),
            float(case.previous_same_zone),
            1.0 if case.recurrence_same_zone else 0.0,
            _load_band_num(case.training_load_band),
            float(case.days_since_last_intense),
        ],
        dtype=float,
    )


def _absence_vector(case: PhysioHistoricalCase) -> np.ndarray:
    return np.array(
        [
            float(case.age),
            float(case.previous_same_zone),
            1.0 if case.recurrence_same_zone else 0.0,
            _load_band_num(case.training_load_band),
            float(case.absence_days),
        ],
        dtype=float,
    )


def _target_risk_vector(payload: Dict) -> np.ndarray:
    return np.array(
        [
            float(payload.get("age", 25)),
            float(payload.get("previous_injuries", 0)),
            float(payload.get("injuries_last_2_seasons", 0)),
            1.0 if payload.get("recurrence_same_zone") else 0.0,
            _load_band_num(payload.get("training_load_band", "medium")),
            float(payload.get("days_since_last_intense", 2)),
        ],
        dtype=float,
    )


def _target_absence_vector(payload: Dict) -> np.ndarray:
    return np.array(
        [
            float(payload.get("age", 25)),
            float(payload.get("previous_same_zone", 0)),
            1.0 if payload.get("recurrence_same_zone") else 0.0,
            _load_band_num(payload.get("training_load_band", "medium")),
            float(payload.get("absence_anchor_days", 21)),
        ],
        dtype=float,
    )


def _match_pct_from_distance(distance: float) -> float:
    score = 1.0 / (1.0 + max(distance, 0.0))
    return round(score * 100.0, 1)


def _format_case_summary(case: PhysioHistoricalCase) -> str:
    pos = case.position if case.position and case.position.lower() != 'unknown' else 'Player'
    return (
        f"{case.player_name} ({pos} · Age {case.age}) · {case.injury_type} "
        f"{('recurrence' if case.recurrence_same_zone else 'non-recurrence')}"
    )


def _top_k(cases: Iterable[PhysioHistoricalCase], target: np.ndarray, mode: str, k: int = 3) -> List[SimilarityResult]:
    pairs = []
    for case in cases:
        vec = _injury_vector(case) if mode == "risk" else _absence_vector(case)
        distance = float(np.linalg.norm(target - vec))
        pairs.append((case, distance))

    pairs.sort(key=lambda x: x[1])

    # Pre-filter to unique players
    unique_pairs = []
    seen_names = set()
    for case, dist in pairs:
        if case.player_name not in seen_names:
            seen_names.add(case.player_name)
            unique_pairs.append((case, dist))

    out: List[SimilarityResult] = []
    selected_cases = []

    for idx in range(1, k + 1):
        if not unique_pairs:
            break
            
        best_idx = 0
        best_score = float('inf')
        
        for i, (case, dist) in enumerate(unique_pairs):
            penalty = 0.0
            
            # Penalize if we already picked a case with identical absence days
            if any(c.absence_days == case.absence_days for c in selected_cases):
                penalty += 1.5
                
            # Disfavor exact same injury text if possible
            if any(c.injury_type == case.injury_type for c in selected_cases):
                penalty += 0.5
                
            # Disfavor same club string
            c_club = case.metadata.get("club") if isinstance(case.metadata, dict) else None
            if c_club and any(
                isinstance(c.metadata, dict) and c.metadata.get("club") == c_club 
                for c in selected_cases
            ):
                penalty += 0.5
                
            score = dist + penalty
            if score < best_score:
                best_score = score
                best_idx = i
                
        case, dist = unique_pairs.pop(best_idx)
        selected_cases.append(case)

        out.append(
            SimilarityResult(
                case_id=case.id,
                rank=idx,
                distance=round(dist, 4),
                match_pct=_match_pct_from_distance(dist),
                summary=_format_case_summary(case),
                payload={
                    "player_name": case.player_name,
                    "age": case.age,
                    "position": case.position,
                    "injury_type": case.injury_type,
                    "previous_injuries": case.previous_injuries,
                    "previous_same_zone": case.previous_same_zone,
                    "recurrence_same_zone": case.recurrence_same_zone,
                    "training_load_band": case.training_load_band,
                    "absence_days": case.absence_days,
                },
            )
        )
    return out

def similar_for_risk(payload: Dict, k: int = 3) -> List[SimilarityResult]:
    qs = PhysioHistoricalCase.objects.all().order_by("-created_at")[:3000]
    if not qs:
        return []
    target = _target_risk_vector(payload)
    return _top_k(qs, target, "risk", k=k)



def similar_for_absence(payload: Dict, k: int = 3) -> List[SimilarityResult]:
    qs = PhysioHistoricalCase.objects.all().order_by("-created_at")[:3000]
    if not qs:
        return []
    target = _target_absence_vector(payload)
    return _top_k(qs, target, "absence", k=k)
