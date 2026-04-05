"""
nutrition_logic.py
==================
All sports-science calculations for NutriAI.

Units follow the international sports nutrition convention:
  - macros expressed as g/kg body weight (not flat grams)
  - energy in kcal
  - micronutrients in mg or g as specified

References
----------
- Mifflin-St Jeor (1990) — BMR formula
- ISSN Position Stand: Nutrient Timing (2017)
- BJSM: Nutritional Support for Injury Recovery (2015)
- IOC Consensus Statement: Dietary Supplements in Athletes (2018)
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Baseline physiological parameters
# ─────────────────────────────────────────────────────────────────────────────

# TDEE activity multipliers keyed by plan day_type
DAY_MULTIPLIERS: dict[str, float] = {
    'match':    1.9,   # match day: very high demand
    'training': 1.7,   # structured training session
    'rest':     1.4,   # active rest / recovery
}

# Position-based activity factor adjustment (additive to DAY_MULTIPLIER)
POSITION_FACTOR: dict[str, float] = {
    'GK':  -0.05,
    'CB':   0.00,
    'RB':   0.05,
    'LB':   0.05,
    'CDM':  0.05,
    'CM':   0.05,
    'CAM':  0.07,
    'RW':   0.08,
    'LW':   0.08,
    'FW':   0.08,
    'ST':   0.08,
}

# Sports-science carbohydrate targets (g/kg) by day type — baseline
BASE_CARB_G_PER_KG: dict[str, float] = {
    'match':    8.0,   # competition day
    'training': 5.0,   # moderate-high training
    'rest':     3.0,   # recovery / low-intensity
}

# Protein targets (g/kg) — ISSN recommendation for athletes
PROTEIN_G_PER_KG: dict[str, float] = {
    'maintain': 1.8,
    'bulk':     2.2,
    'cut':      2.4,   # preserve LBM during caloric deficit
}

# Fat targets (g/kg) — essential minimum + performance allocation
FAT_G_PER_KG: dict[str, float] = {
    'maintain': 1.2,
    'bulk':     1.0,
    'cut':      0.9,
}

# ─────────────────────────────────────────────────────────────────────────────
# Recovery micronutrient protocols (BJSM evidence-based)
# ─────────────────────────────────────────────────────────────────────────────

RECOVERY_PROTOCOLS: dict[str, dict[str, Any]] = {
    'mild': {
        'focus': (
            'Maintain normal caloric intake. Increase Vitamin C (500 mg/day) '
            'and Zinc (15 mg/day) to support tissue repair. '
            'Prioritise omega-3 fatty acids (2 g/day EPA+DHA).'
        ),
        'collagen_g':     10,
        'zinc_mg':        15,
        'omega3_g':        2,
        'vitamin_c_mg':  500,
        'creatine_g':      0,
        'protein_g_per_kg_boost': 0.2,
        'carb_reduction_pct': 0,
        'meal_timing': (
            'Distribute protein across 4 meals (0.4 g/kg/meal). '
            'Pre-sleep casein (40 g) to maximise overnight repair.'
        ),
        'anti_doping_note': (
            'Collagen and Zinc supplements must carry an Informed Sport '
            'or Informed Choice batch-tested certification.'
        ),
    },
    'moderate': {
        'focus': (
            'Increase Collagen peptides (15 g/day taken with Vitamin C 1000 mg '
            'pre-exercise for enhanced synthesis). Zinc 25 mg/day. '
            'Omega-3 EPA+DHA 3 g/day to reduce inflammation. '
            'Protein maintained at 2.2 g/kg despite reduced activity.'
        ),
        'collagen_g':     15,
        'zinc_mg':        25,
        'omega3_g':        3,
        'vitamin_c_mg': 1000,
        'creatine_g':      0,
        'protein_g_per_kg_boost': 0.4,
        'carb_reduction_pct': 15,
        'meal_timing': (
            'Reduce overall carbohydrate by 15% (lower activity). '
            'Pre-sleep casein 40 g every night. '
            'Collagen + Vitamin C 60 min before physio.'
        ),
        'anti_doping_note': (
            'All supplements must be Informed Sport certified. '
            'Document batch numbers in the supplementation log.'
        ),
    },
    'severe': {
        'focus': (
            'Medical-grade collagen peptides 20 g/day + Vitamin C 1000 mg. '
            'Creatine monohydrate 5 g/day to prevent immobilisation muscle atrophy (Cochrane 2021). '
            'Zinc 30 mg/day. Omega-3 EPA+DHA 4 g/day. '
            'Maintain FULL TDEE intake — caloric deficit accelerates muscle loss during immobilisation.'
        ),
        'collagen_g':     20,
        'zinc_mg':        30,
        'omega3_g':        4,
        'vitamin_c_mg': 1000,
        'creatine_g':      5,
        'protein_g_per_kg_boost': 0.6,
        'carb_reduction_pct': 0,   # maintain calories; muscle preservation priority
        'meal_timing': (
            'Distribute across 5 meals (every 3 h). '
            'Creatine with carbohydrate meal for enhanced uptake. '
            'Pre-sleep casein 50 g. '
            'Medical nutrition support: liaise with club physician.'
        ),
        'anti_doping_note': (
            'CRITICAL: Creatine must be Informed Sport certified. '
            'Record batch number, expiry, lot number for anti-doping forensic audit trail. '
            'Inform player of WADA Prohibited List status of all compounds.'
        ),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Core calculations
# ─────────────────────────────────────────────────────────────────────────────

def bmr_mifflin(weight_kg: float, height_cm: float, age: int, is_male: bool = True) -> float:
    """
    Mifflin-St Jeor BMR (1990).

    Parameters
    ----------
    weight_kg : float
    height_cm : float
    age       : int
    is_male   : bool

    Returns
    -------
    float — BMR in kcal/day
    """
    if is_male:
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161


def compute_tdee(
    weight_kg: float,
    height_cm: float,
    age: int,
    is_male: bool,
    day_type: str,
    position: str = '',
) -> float:
    """
    Total Daily Energy Expenditure = BMR × activity multiplier × position factor.

    Returns
    -------
    float — TDEE in kcal/day
    """
    bmr  = bmr_mifflin(weight_kg, height_cm, age, is_male)
    mult = DAY_MULTIPLIERS.get(day_type, 1.7)
    pos  = POSITION_FACTOR.get(position, 0.0)
    return bmr * (mult + pos)


def dynamic_carbs_from_load(
    player,
    date_for_plan: date,
    weight_kg: float,
    day_type: str,
    lookback_days: int = 28,
) -> tuple[float, float, str]:
    """
    Query the player's recent TrainingLoad history and adjust carbohydrate
    targets based on the 20th/80th load percentile (sports science periodisation).

    The most recent session's ``total_distance_km`` is compared against
    historical percentiles:
      - > 80th percentile → HIGH LOAD → 7 g/kg body weight
      - < 20th percentile → LOW LOAD  → 3 g/kg body weight
      - otherwise        → NORMAL    → ``BASE_CARB_G_PER_KG[day_type]``

    Parameters
    ----------
    player         : scout.models.Player instance
    date_for_plan  : date  — the plan date (used to bound the history query)
    weight_kg      : float — player body weight in kg
    day_type       : str   — 'match' | 'training' | 'rest'
    lookback_days  : int   — window size for percentile computation

    Returns
    -------
    (carbs_g, carbs_g_per_kg, load_band)
      carbs_g       : float — absolute carbs in grams
      carbs_g_per_kg: float — carb density (g per kg BW)
      load_band     : str   — 'high_load' | 'low_load' | 'normal' | 'insufficient_data'
    """
    # Late import to avoid circular dependency at module load time
    from physio.models import TrainingLoad

    cutoff = date_for_plan - timedelta(days=lookback_days)
    loads  = list(
        TrainingLoad.objects
        .filter(player=player, date__gt=cutoff)
        .order_by('-date')
        .values_list('total_distance_km', flat=True)
    )

    base_g_per_kg = BASE_CARB_G_PER_KG.get(day_type, 5.0)

    if len(loads) < 3:
        # Insufficient history — fall back to base target
        carbs_g = base_g_per_kg * weight_kg
        return round(carbs_g, 1), base_g_per_kg, 'insufficient_data'

    arr       = np.array(loads, dtype=float)
    p20       = float(np.percentile(arr, 20))
    p80       = float(np.percentile(arr, 80))
    last_load = float(arr[0])  # most recent session

    if last_load > p80:
        g_per_kg  = 7.0    # high load: 80th percentile → 7 g/kg
        load_band = 'high_load'
    elif last_load < p20:
        g_per_kg  = 3.0    # low load: 20th percentile → 3 g/kg
        load_band = 'low_load'
    else:
        g_per_kg  = base_g_per_kg
        load_band = 'normal'

    carbs_g = g_per_kg * weight_kg
    return round(carbs_g, 1), g_per_kg, load_band


def get_active_injury(player) -> 'Any | None':
    """
    Return the most recent active Injury for this player, or None.
    An injury is considered 'active' if it was recorded within the last
    ``days_absent`` days (i.e., expected recovery not yet reached).
    """
    from physio.models import Injury

    today = date.today()
    # Get all injuries, check if recovery window hasn't elapsed
    injuries = (
        Injury.objects.filter(player=player)
        .order_by('-date')[:10]
    )
    for inj in injuries:
        if not inj.days_absent:
            # No duration recorded — assume still active if within 30 days
            if (today - inj.date).days <= 30:
                return inj
        else:
            expected_return = inj.date + timedelta(days=inj.days_absent)
            if today <= expected_return:
                return inj
    return None


def build_recovery_nutrients(injury) -> dict[str, Any]:
    """
    Build the ``recovery_nutrients`` response dict from an active Injury.

    Parameters
    ----------
    injury : physio.models.Injury

    Returns
    -------
    dict with keys: severity, injury_type, focus, protocol, anti_doping_note, …
    """
    sev      = injury.severity if injury.severity in RECOVERY_PROTOCOLS else 'mild'
    protocol = RECOVERY_PROTOCOLS[sev]
    return {
        'active_injury':    injury.injury_type,
        'severity':         sev,
        'focus':            protocol['focus'],
        'collagen_g_day':   protocol['collagen_g'],
        'zinc_mg_day':      protocol['zinc_mg'],
        'omega3_g_day':     protocol['omega3_g'],
        'vitamin_c_mg_day': protocol['vitamin_c_mg'],
        'creatine_g_day':   protocol.get('creatine_g', 0),
        'carb_reduction_pct': protocol['carb_reduction_pct'],
        'protein_g_per_kg_boost': protocol['protein_g_per_kg_boost'],
        'meal_timing':      protocol['meal_timing'],
        'anti_doping_note': protocol['anti_doping_note'],
    }


def live_dinner_feedback(total_distance_km: float, weight_kg: float) -> dict[str, Any]:
    """
    Real-time post-session dinner carbohydrate recommendation.

    Sports science rationale:
      - After sessions > 10 km the glycogen stores are substantially depleted.
      - Immediate post-exercise CHO "window": 1.0–1.2 g/(kg·h) for 4 h.
      - This function returns the dinner top-up (the 4-h window component).

    Parameters
    ----------
    total_distance_km : float — most recent session distance
    weight_kg         : float — player body weight

    Returns
    -------
    dict with dinner adjustment details
    """
    if total_distance_km > 10.0:
        # 1.0 g/kg for each km above 10km, capped at 3.0 g/kg
        extra_g_per_kg = min((total_distance_km - 10.0) * 0.1 + 1.0, 3.0)
        extra_g        = round(extra_g_per_kg * weight_kg, 0)
        return {
            'dinner_adjustment':  True,
            'extra_carbs_g':      extra_g,
            'extra_carbs_g_per_kg': round(extra_g_per_kg, 2),
            'distance_km':        total_distance_km,
            'recommended_foods': [
                f'White rice ~{int(extra_g * 1.4)}g cooked',
                'Sports recovery drink (60g carbs)',
                'Banana x2',
                'White bread with honey',
            ],
            'note': (
                f'Post-{total_distance_km:.1f} km session: add '
                f'{extra_g:.0f} g CHO (~{extra_g_per_kg:.1f} g/kg) to dinner '
                f'within 60 min of final whistle.'
            ),
            'timing': 'Consume within 0–60 min post-session for optimal glycogen resynthesis.',
        }
    return {
        'dinner_adjustment':  False,
        'extra_carbs_g':      0,
        'distance_km':        total_distance_km,
        'note':               'Standard dinner macros apply. Session distance < 10 km.',
    }


def build_full_macro_plan(
    weight_kg: float,
    height_cm: float,
    age: int,
    is_male: bool,
    day_type: str,
    goal: str,
    position: str,
    carbs_g: float,
    recovery_nutrients: 'dict | None',
) -> dict[str, Any]:
    """
    Compile the final macro targets given all contextual inputs.
    Returns a dict suitable for `DailyPlan` creation and API response augmentation.
    """
    tdee = compute_tdee(weight_kg, height_cm, age, is_male, day_type, position)

    # Protein: g/kg scaled by goal
    prot_gkg = PROTEIN_G_PER_KG.get(goal, 1.8)
    if recovery_nutrients:
        prot_gkg += recovery_nutrients.get('protein_g_per_kg_boost', 0)
    protein_g = round(prot_gkg * weight_kg, 1)

    # Carbs: dynamic (already computed by caller)
    # Apply recovery carb reduction if applicable
    if recovery_nutrients and recovery_nutrients.get('carb_reduction_pct', 0) > 0:
        reduction = 1.0 - (recovery_nutrients['carb_reduction_pct'] / 100.0)
        carbs_g   = round(carbs_g * reduction, 1)

    # Fat: from g/kg target
    fat_g = round(FAT_G_PER_KG.get(goal, 1.2) * weight_kg, 1)

    # Adjusted total calories from macros (more accurate than raw TDEE)
    total_kcal = round(carbs_g * 4 + protein_g * 4 + fat_g * 9, 1)

    return {
        'calories':   total_kcal,
        'protein_g':  protein_g,
        'carbs_g':    carbs_g,
        'fat_g':      fat_g,
        'protein_g_per_kg': round(prot_gkg, 2),
        'carbs_g_per_kg':   round(carbs_g / weight_kg, 2) if weight_kg else 0,
        'fat_g_per_kg':     round(fat_g / weight_kg, 2)   if weight_kg else 0,
        'tdee_estimate':    round(tdee, 1),
    }
