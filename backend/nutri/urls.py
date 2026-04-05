from django.urls import path
from .views import (
    FoodListCreateView, FoodDetailView, SportsFoodFiltersView,
    DailyPlanListCreateView,
    MealCalcView, GeneratePlanView,
    LiveFeedbackView,
    MealLogListCreateView, MealLogDetailView, MealLogTotalsView,
    SupplementListCreateView, SupplementDetailView,
)

urlpatterns = [
    # ── Food database ────────────────────────────────────────────────────────
    path('foods/',                     FoodListCreateView.as_view()),
    path('foods/<int:pk>/',            FoodDetailView.as_view()),
    path('food-filters/',              SportsFoodFiltersView.as_view()),

    # ── Daily plans ───────────────────────────────────────────────────────────
    path('plans/',                     DailyPlanListCreateView.as_view()),
    path('generate-plan/',             GeneratePlanView.as_view()),

    # ── Meal calculator ───────────────────────────────────────────────────────
    path('meal-calc/',                 MealCalcView.as_view()),

    # ── Live post-session feedback ────────────────────────────────────────────
    path('live-feedback/',             LiveFeedbackView.as_view()),

    # ── Meal log (actual vs target) ───────────────────────────────────────────
    path('meal-logs/',                 MealLogListCreateView.as_view()),
    path('meal-logs/<int:pk>/',        MealLogDetailView.as_view()),
    path('meal-logs/totals/',          MealLogTotalsView.as_view()),

    # ── Supplement tracker ────────────────────────────────────────────────────
    path('supplements/',               SupplementListCreateView.as_view()),
    path('supplements/<int:pk>/',      SupplementDetailView.as_view()),
]