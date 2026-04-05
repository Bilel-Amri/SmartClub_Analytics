"""
SmartClub tool functions — called by the LLM agent.
Each returns a dict with 'ok': True/False and 'data' or 'error'.
All data fetched via Django ORM (no HTTP self-calls → no auth issues).
"""
from __future__ import annotations
import time
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Internal helper
# ─────────────────────────────────────────────────────────────────────────────

def _timed(fn, *args, **kwargs) -> tuple[Any, int]:
    """Run fn(*args, **kwargs), return (result, latency_ms)."""
    t0 = time.monotonic()
    result = fn(*args, **kwargs)
    return result, int((time.monotonic() - t0) * 1000)


# ─────────────────────────────────────────────────────────────────────────────
# 1. player_search
# ─────────────────────────────────────────────────────────────────────────────

def player_search(query: str = '', scope: str = 'club', limit: int = 10) -> dict:
    """
    Search players by name.  Pass query='' or query='*' to list the whole squad.
    scope='club'   → Club (Scout) players
    scope='global' → SoccerMon GlobalPlayers
    """
    query = (query or '').strip().lstrip('*').strip()  # '*' → ''

    if scope == 'global':
        from physio.models import GlobalPlayer
        qs = (GlobalPlayer.objects.filter(external_id__icontains=query)
              if query else GlobalPlayer.objects.all())
        qs = qs[:limit]
        results = [{'id': str(p.external_id), 'name': p.external_id, 'team': p.team}
                   for p in qs]
    else:
        from scout.models import Player
        qs = (Player.objects.filter(full_name__icontains=query)
              if query else Player.objects.all())
        qs = qs.order_by('full_name')[:limit]
        results = [
            {
                'id': p.id,
                'name': p.full_name,
                'position': p.position,
                'age': p.age,
                'club': p.current_club,
            }
            for p in qs
        ]

    if not results:
        msg = f'No players found matching "{query}"' if query else 'No players in the database yet.'
        return {'ok': False, 'error': msg, 'candidates': []}
    return {'ok': True, 'data': results, 'total': len(results)}


# ─────────────────────────────────────────────────────────────────────────────
# 2. physio_risk
# ─────────────────────────────────────────────────────────────────────────────

def physio_risk(player_id: int | str, horizon_days: int = 7,
                scope: str = 'club') -> dict:
    """
    Return the latest injury-risk prediction and medical prescription.
    scope='club'   -> InjuryRiskPrediction (Club player)
    scope='global' -> Calls the real-time AI Risk Engine for GlobalPlayers
    """
    if scope == 'global':
        from physio.models import GlobalPlayer
        from physio.views import GlobalRiskView
        import datetime
        from django.test import RequestFactory
        
        # 1. Resolve player
        player = None
        if isinstance(player_id, str):
             # Usually 'Veteran (CB) #21'
             player = GlobalPlayer.objects.filter(external_id__icontains=player_id).first()
        if not player:
             try:
                 player = GlobalPlayer.objects.get(pk=int(player_id))
             except:
                 pass
                 
        if not player:
             return {'ok': False, 'error': f'Global profile matching "{player_id}" not found.'}
             
        try:
             # Mock a request to the Risk Engine
             mock_req = type('Request', (), {'query_params': {'horizon': str(horizon_days)}, 'user': type('U', (), {'is_authenticated': True, 'role': 'admin'})()})()
             risk_res = GlobalRiskView().get(mock_req, player.id)
             if hasattr(risk_res, 'status_code') and risk_res.status_code != 200:
                  return {'ok': False, 'error': 'Risk engine unavailable.'}
             r = risk_res.data
             return {
                 'ok': True,
                 'data': {
                      'player_id': r.get('player_id'),
                      'player_name': r.get('external_id'),
                      'risk_band': str(r.get('risk_band', '')).upper(),
                      'risk_prob_pct': r.get('risk_pct'),
                      'top_driver': r.get('top_factor'),
                      'recommended_action': r.get('recommended_action'),
                      'monitoring_note': r.get('monitoring_note'),
                      'llm_directive': "Summarize this status professionally to the user. If the risk is HIGH, urgently advise the prescribed action."
                 }
             }
        except Exception as e:
             return {'ok': False, 'error': f'Risk Engine API Error: {str(e)}'}

    from physio.models import InjuryRiskPrediction, Player
    try:
        player_id = int(player_id)
        player = Player.objects.get(pk=player_id)
    except (ValueError, Player.DoesNotExist):
        return {'ok': False, 'error': f'Player id={player_id} not found'}

    pred = (
        InjuryRiskPrediction.objects
        .filter(player=player, horizon_days=horizon_days)
        .order_by('-predicted_at')
        .first()
    )
    if pred is None:
        # Try any horizon
        pred = (
            InjuryRiskPrediction.objects
            .filter(player=player)
            .order_by('-predicted_at')
            .first()
        )
        if pred is None:
            return {
                'ok': False,
                'error': (
                    f'No risk prediction found for {player.full_name}. '
                    'Go to PhysioAI -> Risk tab -> run Predict Risk first.'
                ),
            }

    return {
        'ok': True,
        'data': {
            'player_id': player.id,
            'player_name': player.full_name,
            'horizon_days': pred.horizon_days,
            'risk_probability': round(pred.risk_probability, 4),
            'risk_band': pred.risk_band,
            'confidence_band': pred.confidence_band,
            'top_factors': pred.shap_factors[:5] if pred.shap_factors else [],
            'recommended_action': pred.recommended_action,
            'monitoring_note': pred.monitoring_note,
            'flag_for_review': pred.flag_for_physio_review,
            'predicted_at': pred.predicted_at.isoformat(),
        },
    }

def physio_timeseries(player_id: int | str, metrics: list[str] | None = None,
                      scope: str = 'club', days: int = 14) -> dict:
    """
    Return recent training-load / wellness time-series for a player.
    scope='club'   → TrainingLoad records
    scope='global' → GlobalDailyRecord records
    """
    if metrics is None:
        metrics = ['total_distance_km', 'rpe', 'sleep_quality']

    if scope == 'global':
        from physio.models import GlobalPlayer, GlobalDailyRecord
        player_id = str(player_id)
        try:
            player = GlobalPlayer.objects.get(external_id=player_id)
        except GlobalPlayer.DoesNotExist:
            return {'ok': False, 'error': f'GlobalPlayer "{player_id}" not found'}

        records = (
            GlobalDailyRecord.objects
            .filter(player=player)
            .order_by('-date')[:days]
        )
        series = []
        for r in reversed(list(records)):
            row = {'date': r.date.isoformat()}
            for m in metrics:
                row[m] = getattr(r, m, None)
            series.append(row)
        return {'ok': True, 'player': player.external_id, 'data': series}

    else:
        from physio.models import TrainingLoad
        from scout.models import Player
        try:
            player = Player.objects.get(pk=int(player_id))
        except (ValueError, Player.DoesNotExist):
            return {'ok': False, 'error': f'Player id={player_id} not found'}

        records = (
            TrainingLoad.objects
            .filter(player=player)
            .order_by('-date')[:days]
        )
        allowed = {'total_distance_km', 'rpe', 'sleep_quality',
                   'sprints', 'accelerations', 'minutes_played'}
        safe_metrics = [m for m in metrics if m in allowed]
        if not safe_metrics:
            safe_metrics = ['total_distance_km', 'rpe', 'sleep_quality']

        series = []
        for r in reversed(list(records)):
            row = {'date': r.date.isoformat()}
            for m in safe_metrics:
                row[m] = getattr(r, m, None)
            series.append(row)
        return {
            'ok': True,
            'player': player.full_name,
            'data': series,
            'metrics': safe_metrics,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 4. nutri_generate_plan
# ─────────────────────────────────────────────────────────────────────────────

def nutri_generate_plan(player_id: int, day_type: str = 'training',
                        goal: str = 'maintain') -> dict:
    """
    Return the latest daily nutrition plan for a player, or generate a new one
    by calling the NutriAI calculation logic directly.
    """
    from scout.models import Player
    from nutri.models import DailyPlan
    import datetime

    try:
        player = Player.objects.get(pk=int(player_id))
    except (ValueError, Player.DoesNotExist):
        return {'ok': False, 'error': f'Player id={player_id} not found'}

    # Check for existing plan today
    today = datetime.date.today()
    plan = DailyPlan.objects.filter(
        player=player, day_type=day_type, goal=goal
    ).order_by('-date').first()

    if plan:
        return {
            'ok': True,
            'data': {
                'player_name': player.full_name,
                'date': str(plan.date),
                'day_type': plan.day_type,
                'goal': plan.goal,
                'calories': round(plan.calories, 0),
                'protein_g': round(plan.protein_g, 1),
                'carbs_g': round(plan.carbs_g, 1),
                'fat_g': round(plan.fat_g, 1),
                'notes': plan.notes,
            },
        }
    else:
        return {
            'ok': False,
            'error': (
                f'No nutrition plan found for {player.full_name} '
                f'(day_type={day_type}, goal={goal}). '
                'Go to NutriAI → Generate Plan to create one.'
            ),
        }


# ─────────────────────────────────────────────────────────────────────────────
# 5. nutri_meal_calc
# ─────────────────────────────────────────────────────────────────────────────

def nutri_meal_calc(items: list[dict]) -> dict:
    """
    Calculate calories + macros for a list of {food_name|food_id, grams}.
    """
    from nutri.models import Food

    if not items:
        return {'ok': False, 'error': 'items list is required'}

    total = {'calories': 0.0, 'protein_g': 0.0, 'carbs_g': 0.0, 'fat_g': 0.0}
    breakdown = []
    errors = []

    for item in items:
        grams = float(item.get('grams', 100))
        food = None

        if 'food_id' in item:
            try:
                food = Food.objects.get(pk=int(item['food_id']))
            except (ValueError, Food.DoesNotExist):
                errors.append(f'food_id={item["food_id"]} not found')
                continue
        elif 'food_name' in item:
            food = Food.objects.filter(name__icontains=item['food_name']).first()
            if not food:
                errors.append(f'food "{item["food_name"]}" not found')
                continue

        if food:
            factor = grams / 100.0
            cal  = round(food.calories_100g * factor, 1)
            prot = round(food.protein_100g  * factor, 1)
            carb = round(food.carbs_100g    * factor, 1)
            fat  = round(food.fat_100g      * factor, 1)
            total['calories']  += cal
            total['protein_g'] += prot
            total['carbs_g']   += carb
            total['fat_g']     += fat
            breakdown.append({
                'food': food.name,
                'grams': grams,
                'calories': cal,
                'protein_g': prot,
                'carbs_g': carb,
                'fat_g': fat,
            })

    result = {
        'ok': len(breakdown) > 0,
        'total': {k: round(v, 1) for k, v in total.items()},
        'breakdown': breakdown,
    }
    if errors:
        result['warnings'] = errors
    if not breakdown:
        result['error'] = 'No valid food items found. ' + '; '.join(errors)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 6. food_search
# ─────────────────────────────────────────────────────────────────────────────

def food_search(query: str, limit: int = 8) -> dict:
    """Search the food database by name."""
    from nutri.models import Food
    query = (query or '').strip()
    if not query:
        return {'ok': False, 'error': 'query is required'}

    foods = Food.objects.filter(name__icontains=query)[:limit]
    if not foods:
        return {'ok': False, 'error': f'No foods found matching "{query}"'}
    return {
        'ok': True,
        'data': [
            {
                'id': f.id,
                'name': f.name,
                'calories_100g': f.calories_100g,
                'protein_100g': f.protein_100g,
                'carbs_100g': f.carbs_100g,
                'fat_100g': f.fat_100g,
            }
            for f in foods
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7. squad_risk
# ─────────────────────────────────────────────────────────────────────────────

def squad_risk(horizon_days: int = 7, limit: int = 5, band: str | None = None) -> dict:
    """
    Return the top-N highest-risk players across the whole squad,
    based on the latest InjuryRiskPrediction for each player.
    Optionally filter by band ('HIGH', 'MEDIUM', 'LOW').
    """
    from physio.models import InjuryRiskPrediction
    from scout.models import Player
    from django.db.models import OuterRef, Subquery

    # Latest prediction id per (player, horizon)
    latest_pred = (
        InjuryRiskPrediction.objects
        .filter(player=OuterRef('player'), horizon_days=OuterRef('horizon_days'))
        .order_by('-predicted_at')
        .values('id')[:1]
    )
    qs = (
        InjuryRiskPrediction.objects
        .filter(
            horizon_days=horizon_days,
            id__in=Subquery(
                InjuryRiskPrediction.objects
                .filter(horizon_days=horizon_days)
                .annotate(latest_id=Subquery(
                    InjuryRiskPrediction.objects
                    .filter(player=OuterRef('player'), horizon_days=horizon_days)
                    .order_by('-predicted_at')
                    .values('id')[:1]
                ))
                .filter(id=Subquery(
                    InjuryRiskPrediction.objects
                    .filter(player=OuterRef('player'), horizon_days=horizon_days)
                    .order_by('-predicted_at')
                    .values('id')[:1]
                ))
                .values('id')
            )
        )
        .select_related('player')
        .order_by('-risk_probability')
    )

    if band:
        qs = qs.filter(risk_band__iexact=band)

    qs = qs[:limit]
    results = list(qs)

    if not results:
        return {
            'ok': False,
            'error': (
                f'No injury risk predictions found for {horizon_days}d horizon. '
                'Go to PhysioAI → Risk tab → run Predict Risk for the squad first.'
            ),
        }

    return {
        'ok': True,
        'horizon_days': horizon_days,
        'data': [
            {
                'rank': i + 1,
                'player_id': p.player.id,
                'player_name': p.player.full_name,
                'risk_probability': round(p.risk_probability, 4),
                'risk_band': p.risk_band,
                'recommended_action': p.recommended_action,
                'top_factors': (p.shap_factors or [])[:3],
                'predicted_at': p.predicted_at.isoformat(),
            }
            for i, p in enumerate(results)
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Registry — maps tool_name → function and OpenAI schema
# ─────────────────────────────────────────────────────────────────────────────

TOOL_REGISTRY = {
    'player_search': player_search,
    'physio_risk': physio_risk,
    'squad_risk': squad_risk,
    'physio_timeseries': physio_timeseries,
    'nutri_generate_plan': nutri_generate_plan,
    'nutri_meal_calc': nutri_meal_calc,
    'food_search': food_search,
}

TOOL_SCHEMAS = [
    {
        'type': 'function',
        'function': {
            'name': 'player_search',
            'description': (
                'Search for players by name, or list the FULL squad. '
                'Use for: "show all players", "list players", "find player X", "who is in the squad", '
                '"search for [name]", "show me the roster", "effectif", "liste des joueurs". '
                'Pass query="" to list ALL players. Pass a name to search by name.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'query':  {'type': 'string',
                               'description': 'Player name or partial name. Leave empty ("") to list the whole squad.'},
                    'scope':  {'type': 'string', 'enum': ['club', 'global'], 'description': 'Data scope'},
                    'limit':  {'type': 'integer', 'description': 'Max results (default 10)', 'default': 10},
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'physio_risk',
            'description': (
                'Get the ML injury risk prediction for ONE specific player. '
                'Use for: "injury risk for [player]", "is [player] at risk?", "predict injury for [player]", '
                '"risque de blessure pour [joueur]", "khtour mta3 [joueur]". '
                'Requires player_id — call player_search first if you only have the name.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'player_id':    {'type': 'integer', 'description': 'Club player primary key (get from player_search first)'},
                    'horizon_days': {'type': 'integer', 'enum': [7, 30], 'description': '7-day or 30-day prediction horizon'},
                    'scope':        {'type': 'string', 'enum': ['club', 'global']},
                },
                'required': ['player_id'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'physio_timeseries',
            'description': (
                'Get training load and wellness time-series data for ONE player. '
                'Use for: "training load for [player]", "ACWR trend for [player]", "is [player] overloaded?", '
                '"show distance/RPE/sleep for [player]", "charge d\'entraînement de [joueur]", '
                '"fatigue de [joueur]", "last 2 weeks data", "historical load". '
                'Returns daily metrics: distance, RPE, sleep quality, sprints, ACWR, ATL, CTL28.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'player_id': {'type': 'integer', 'description': 'Player id (get from player_search first if needed)'},
                    'metrics':   {
                        'type': 'array',
                        'items': {'type': 'string',
                                  'enum': ['total_distance_km', 'rpe', 'sleep_quality',
                                           'sprints', 'accelerations', 'minutes_played',
                                           'acwr', 'daily_load', 'atl', 'ctl28', 'monotony', 'strain']},
                        'description': 'Which metrics to return. Default: distance, rpe, sleep.',
                    },
                    'scope': {'type': 'string', 'enum': ['club', 'global']},
                    'days':  {'type': 'integer', 'description': 'Days to look back (default 14, max 60)'},
                },
                'required': ['player_id'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'nutri_generate_plan',
            'description': (
                'Get the nutrition plan (calories + macros) for a specific player. '
                'Use for: "nutrition plan for [player]", "how many calories for [player]?", '
                '"what should [player] eat?", "macros for [player] on match day", '
                '"plan nutritionnel pour [joueur]", "calories mta3 [joueur]". '
                'Specify day_type (match/training/rest) and goal (maintain/bulk/cut).'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'player_id': {'type': 'integer', 'description': 'Player id'},
                    'day_type':  {'type': 'string', 'enum': ['match', 'training', 'rest'],
                                  'description': 'Type of day (default: training)'},
                    'goal':      {'type': 'string', 'enum': ['maintain', 'bulk', 'cut'],
                                  'description': 'Nutrition goal (default: maintain)'},
                },
                'required': ['player_id'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'nutri_meal_calc',
            'description': (
                'Calculate total calories and macros for a custom list of foods + weights. '
                'Use for: "how many calories in 150g chicken + 200g rice?", '
                '"calculate macros for this meal", "calcule les macros de ce repas", '
                '"combien de calories dans [aliment]?". '
                'Pass food names and weights in grams.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'items': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'food_name': {'type': 'string', 'description': 'Food name in English'},
                                'food_id':   {'type': 'integer', 'description': 'Food DB id (optional if name given)'},
                                'grams':     {'type': 'number', 'description': 'Weight in grams'},
                            },
                        },
                        'description': 'List of {food_name, grams} pairs',
                    },
                },
                'required': ['items'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'food_search',
            'description': (
                'Search foods in the nutrition database by name. Returns calories + macros per 100g. '
                'Use for: "find foods high in protein", "search for chicken", "what\'s in eggs?", '
                '"aliments riches en protéines", "cherche [aliment]". '
                'Use before nutri_meal_calc if you need a food_id.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {'type': 'string', 'description': 'Food name or keyword to search'},
                    'limit': {'type': 'integer', 'description': 'Max results (default 8)', 'default': 8},
                },
                'required': ['query'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'squad_risk',
            'description': (
                'Return the top-N highest-risk players across the WHOLE squad — use this whenever the user '
                'asks for "top players at risk", "most injured", "highest risk squad", "who is at risk", '
                '"list injured players", "squad injury", "les joueurs à risque", "top 3 risk", etc. '
                'No player name is needed — it scans all predictions at once.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'horizon_days': {'type': 'integer', 'enum': [7, 30],
                                    'description': '7-day or 30-day horizon (default 7)'},
                    'limit':        {'type': 'integer',
                                    'description': 'How many players to return (default 5, use 3 for "top 3")'},
                    'band':         {'type': 'string', 'enum': ['HIGH', 'MEDIUM', 'LOW'],
                                    'description': 'Optional: filter to only HIGH / MEDIUM / LOW risk players'},
                },
                'required': [],
            },
        },
    },
]
