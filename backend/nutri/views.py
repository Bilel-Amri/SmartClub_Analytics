"""
nutri/views.py
==============
NutriAI API views — professional sports nutrition management.

All macro calculation logic lives in nutri/utils/nutrition_logic.py.
Views are kept deliberately thin: validate → delegate → respond.
"""
from __future__ import annotations

import logging

from rest_framework import generics, views
from rest_framework.response import Response

from scout.models import Player

from .models import DailyPlan, Food, MealLog, Supplement
from .serializers import (
    DailyPlanSerializer,
    FoodSerializer,
    GeneratePlanRequestSerializer,
    MealCalcRequestSerializer,
    MealLogCreateSerializer,
    MealLogSerializer,
    SupplementSerializer,
)
from .utils.nutrition_logic import (
    build_full_macro_plan,
    build_recovery_nutrients,
    dynamic_carbs_from_load,
    get_active_injury,
    live_dinner_feedback,
)

logger = logging.getLogger(__name__)

# ─── Common sports food spotlights (for frontend filter chips) ───────────────
SPORTS_FOOD_FILTERS: list[dict] = [
    {'label': 'Chicken',       'query': 'chicken'},
    {'label': 'Pasta',         'query': 'pasta'},
    {'label': 'Whey',          'query': 'whey'},
    {'label': 'Avocado',       'query': 'avocado'},
    {'label': 'Rice',          'query': 'rice'},
    {'label': 'Eggs',          'query': 'egg'},
    {'label': 'Oats',          'query': 'oat'},
    {'label': 'Salmon',        'query': 'salmon'},
    {'label': 'Banana',        'query': 'banana'},
    {'label': 'Sweet Potato',  'query': 'sweet potato'},
    {'label': 'Broccoli',      'query': 'broccoli'},
    {'label': 'Greek Yoghurt', 'query': 'yoghurt'},
]


# ─────────────────────────────────────────────────────────────────────────────
# Food Database
# ─────────────────────────────────────────────────────────────────────────────


class FoodListCreateView(generics.ListCreateAPIView):
    serializer_class = FoodSerializer

    def get_queryset(self):
        qs       = Food.objects.all().order_by('name')
        q        = self.request.query_params.get('q')
        category = self.request.query_params.get('category')  # sports food filter chip
        if q:
            qs = qs.filter(name__icontains=q)
        elif category:
            cat_map = {c['label'].lower(): c['query'] for c in SPORTS_FOOD_FILTERS}
            term    = cat_map.get(category.lower(), category)
            qs      = qs.filter(name__icontains=term)
        return qs


class FoodDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset         = Food.objects.all()
    serializer_class = FoodSerializer


class SportsFoodFiltersView(views.APIView):
    """GET /api/nutri/food-filters/ → return sports food filter chip list."""
    def get(self, request) -> Response:
        return Response({'filters': SPORTS_FOOD_FILTERS})


# ─────────────────────────────────────────────────────────────────────────────
# Daily Plans
# ─────────────────────────────────────────────────────────────────────────────


class DailyPlanListCreateView(generics.ListCreateAPIView):
    queryset         = DailyPlan.objects.select_related('player').order_by('-date')
    serializer_class = DailyPlanSerializer

    def get_queryset(self):
        qs  = super().get_queryset()
        pid = self.request.query_params.get('player')
        if pid:
            qs = qs.filter(player_id=pid)
        return qs


# ─────────────────────────────────────────────────────────────────────────────
# Meal Calculator
# ─────────────────────────────────────────────────────────────────────────────


class MealCalcView(views.APIView):
    """
    POST /api/nutri/meal-calc/
    Pass a list of {food_name|food_id, grams} items; returns macro totals.
    """

    def post(self, request) -> Response:
        ser = MealCalcRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        totals  = {'calories': 0.0, 'protein_g': 0.0, 'carbs_g': 0.0, 'fat_g': 0.0}
        details = []

        for item in ser.validated_data['items']:
            grams = item['grams']
            food  = None
            if item.get('food_id'):
                food = Food.objects.filter(pk=item['food_id']).first()
            elif item.get('food_name') or item.get('name'):
                lookup = item.get('food_name') or item.get('name')
                food   = Food.objects.filter(name__icontains=lookup).first()
            if not food:
                details.append({'name': item.get('name', '?'), 'grams': grams, 'error': 'Not found'})
                continue
            factor = grams / 100.0
            row = {
                'food':      food.name,
                'grams':     grams,
                'calories':  round(food.calories_100g * factor, 1),
                'protein_g': round(food.protein_100g  * factor, 1),
                'carbs_g':   round(food.carbs_100g    * factor, 1),
                'fat_g':     round(food.fat_100g      * factor, 1),
            }
            for k in ('calories', 'protein_g', 'carbs_g', 'fat_g'):
                totals[k] += row[k]
            details.append(row)

        total = {k: round(v, 1) for k, v in totals.items()}
        return Response({
            'items':           details,
            'total':           total,
            'total_calories':  total['calories'],
            'total_protein_g': total['protein_g'],
            'total_carbs_g':   total['carbs_g'],
            'total_fat_g':     total['fat_g'],
            'breakdown':       details,
        })


# ─────────────────────────────────────────────────────────────────────────────
# Generate Plan  ← UPGRADED: training-load sync + injury adaptation
# ─────────────────────────────────────────────────────────────────────────────


class GeneratePlanView(views.APIView):
    """
    POST /api/nutri/generate-plan/

    1. Biometrics from player model (request overrides take priority).
    2. Dynamic carb targets from recent TrainingLoad 20th/80th percentile.
    3. Active Injury detection → appends ``recovery_nutrients`` section.
    4. All math delegated to nutri/utils/nutrition_logic.py.
    """

    def post(self, request) -> Response:
        ser = GeneratePlanRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        pid = d.get('player_id') or d.get('player')
        try:
            player = Player.objects.prefetch_related('training_loads', 'injuries').get(pk=pid)
        except Player.DoesNotExist:
            return Response({'detail': 'Player not found'}, status=404)

        # ── Biometrics ────────────────────────────────────────────────────────
        weight    = float(d.get('weight_kg') or player.weight_kg  or 75.0)
        height    = float(d.get('height_cm') or player.height_cm  or 178.0)
        age       = int(  d.get('age')       or player.age        or 25)
        is_male   = d.get('sex', 'M') == 'M'
        day_type  = d['day_type']
        goal      = d['goal']
        plan_date = d['date']

        # ── Dynamic carb loading from TrainingLoad percentiles ────────────────
        carbs_g, carbs_g_per_kg, load_band = dynamic_carbs_from_load(
            player        = player,
            date_for_plan = plan_date,
            weight_kg     = weight,
            day_type      = day_type,
        )

        # ── Injury adaptation ─────────────────────────────────────────────────
        active_injury      = get_active_injury(player)
        recovery_nutrients = build_recovery_nutrients(active_injury) if active_injury else None

        # ── Full macro computation ────────────────────────────────────────────
        macros = build_full_macro_plan(
            weight_kg          = weight,
            height_cm          = height,
            age                = age,
            is_male            = is_male,
            day_type           = day_type,
            goal               = goal,
            position           = player.position or '',
            carbs_g            = carbs_g,
            recovery_nutrients = recovery_nutrients,
        )

        # ── Notes ─────────────────────────────────────────────────────────────
        load_note = {
            'high_load':         f'🔺 High load (>P80) → carbs {macros["carbs_g_per_kg"]:.1f} g/kg.',
            'low_load':          f'🔻 Low load (<P20) → carbs {macros["carbs_g_per_kg"]:.1f} g/kg.',
            'normal':            f'Standard {macros["carbs_g_per_kg"]:.1f} g/kg ({day_type}).',
            'insufficient_data': '⚠ <3 sessions — base carb targets used.',
        }.get(load_band, '')

        injury_note = (
            f' | 🏥 Recovery Mode: {active_injury.injury_type} ({active_injury.severity})'
            if active_injury else ''
        )

        plan = DailyPlan.objects.create(
            player    = player,
            date      = plan_date,
            day_type  = day_type,
            goal      = goal,
            calories  = macros['calories'],
            protein_g = macros['protein_g'],
            carbs_g   = macros['carbs_g'],
            fat_g     = macros['fat_g'],
            notes     = (
                f'Auto · Mifflin-St Jeor · TDEE≈{macros["tdee_estimate"]:.0f} kcal · '
                f'{load_note}{injury_note}'
            ),
        )

        plan_data = DailyPlanSerializer(plan).data
        plan_data.update({
            'macros_per_kg': {
                'protein_g_per_kg': macros['protein_g_per_kg'],
                'carbs_g_per_kg':   macros['carbs_g_per_kg'],
                'fat_g_per_kg':     macros['fat_g_per_kg'],
            },
            'training_load_context': {
                'load_band':              load_band,
                'carbs_g_per_kg':         carbs_g_per_kg,
                'above_80p_last_session': load_band == 'high_load',
                'below_20p_last_session': load_band == 'low_load',
            },
            'recovery_mode_active': active_injury is not None,
        })
        if recovery_nutrients:
            plan_data['recovery_nutrients'] = recovery_nutrients

        return Response(plan_data, status=201)


# ─────────────────────────────────────────────────────────────────────────────
# Live Post-Session Dinner Feedback
# ─────────────────────────────────────────────────────────────────────────────


class LiveFeedbackView(views.APIView):
    """
    POST /api/nutri/live-feedback/
    { player_id, total_distance_km } → immediate dinner CHO recommendation.
    """

    def post(self, request) -> Response:
        pid      = request.data.get('player_id')
        distance = float(request.data.get('total_distance_km', 0))
        if not pid:
            return Response({'detail': 'player_id is required.'}, status=400)
        try:
            player = Player.objects.get(pk=pid)
        except Player.DoesNotExist:
            return Response({'detail': 'Player not found.'}, status=404)

        weight = float(player.weight_kg or 75.0)
        result = live_dinner_feedback(distance, weight)
        result['player_name'] = player.full_name
        result['weight_kg']   = weight
        return Response(result)


# ─────────────────────────────────────────────────────────────────────────────
# Meal Log  (actual vs target)
# ─────────────────────────────────────────────────────────────────────────────


class MealLogListCreateView(views.APIView):
    """
    GET  /api/nutri/meal-logs/?plan=<id>
    POST /api/nutri/meal-logs/
    """

    def get(self, request) -> Response:
        qs  = MealLog.objects.select_related('food', 'plan__player')
        pid = request.query_params.get('plan')
        if pid:
            qs = qs.filter(plan_id=pid)
        return Response(MealLogSerializer(qs, many=True).data)

    def post(self, request) -> Response:
        ser = MealLogCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            plan = DailyPlan.objects.get(pk=d['plan'])
        except DailyPlan.DoesNotExist:
            return Response({'detail': 'Plan not found.'}, status=404)
        try:
            food = Food.objects.get(pk=d['food'])
        except Food.DoesNotExist:
            return Response({'detail': 'Food not found.'}, status=404)

        log            = MealLog.objects.create(plan=plan, food=food, grams=d['grams'], meal_time=d['meal_time'])
        data           = MealLogSerializer(log).data
        data['day_actual_totals'] = _meal_log_totals(plan)
        return Response(data, status=201)


class MealLogDetailView(generics.RetrieveDestroyAPIView):
    queryset         = MealLog.objects.select_related('food', 'plan')
    serializer_class = MealLogSerializer


class MealLogTotalsView(views.APIView):
    """GET /api/nutri/meal-logs/totals/?plan=<id>  → Target vs Actual for ring chart."""

    def get(self, request) -> Response:
        pid = request.query_params.get('plan')
        if not pid:
            return Response({'detail': 'plan param required.'}, status=400)
        try:
            plan = DailyPlan.objects.get(pk=pid)
        except DailyPlan.DoesNotExist:
            return Response({'detail': 'Plan not found.'}, status=404)

        actual = _meal_log_totals(plan)
        return Response({
            'plan_id':  plan.id,
            'date':     plan.date,
            'day_type': plan.day_type,
            'target': {
                'calories':  plan.calories,
                'protein_g': plan.protein_g,
                'carbs_g':   plan.carbs_g,
                'fat_g':     plan.fat_g,
            },
            'actual': actual,
            'pct': {
                k: round((actual[k] / getattr(plan, k) * 100), 1) if getattr(plan, k) else 0
                for k in ('calories', 'protein_g', 'carbs_g', 'fat_g')
            },
        })


def _meal_log_totals(plan: DailyPlan) -> dict:
    """Aggregate MealLog entries for one plan into macro totals."""
    logs   = MealLog.objects.filter(plan=plan)
    totals = {'calories': 0.0, 'protein_g': 0.0, 'carbs_g': 0.0, 'fat_g': 0.0}
    for log in logs:
        totals['calories']  += log.calories
        totals['protein_g'] += log.protein_g
        totals['carbs_g']   += log.carbs_g
        totals['fat_g']     += log.fat_g
    return {k: round(v, 1) for k, v in totals.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Supplement Tracker  (anti-doping compliance)
# ─────────────────────────────────────────────────────────────────────────────


class SupplementListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/nutri/supplements/?player=<id>
    POST /api/nutri/supplements/

    Response includes an ``anti_doping_warning`` if any supplement lacks
    a valid batch-tested certification — required for WADA/IOC compliance.
    """
    serializer_class = SupplementSerializer

    def get_queryset(self):
        qs  = Supplement.objects.select_related('player').order_by('-date')
        pid = self.request.query_params.get('player')
        if pid:
            qs = qs.filter(player_id=pid)
        return qs

    def list(self, request, *args, **kwargs):
        qs          = self.get_queryset()
        data        = SupplementSerializer(qs, many=True).data
        uncertified = [s for s in data if not s['batch_tested']]
        return Response({
            'supplements':       data,
            'uncertified_count': len(uncertified),
            'anti_doping_warning': (
                f'⚠ WADA/IOC: {len(uncertified)} supplement(s) UNCERTIFIED. '
                'All must carry Informed Sport, BSCG, or NSF batch-tested certification.'
            ) if uncertified else None,
        })


class SupplementDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset         = Supplement.objects.select_related('player')
    serializer_class = SupplementSerializer