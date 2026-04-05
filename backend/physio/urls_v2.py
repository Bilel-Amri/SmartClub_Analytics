from django.urls import path

from .views_v2 import (
    AbsencePredictionView,
    ExplainWithAIView,
    PhysioMLHealthView,
    PlayerRiskSimulatorView,
    SimilaritySeedView,
    SquadDailyRiskView,
    PhysioPlayersProfileView,
)

urlpatterns = [
    path('squad/daily-risk', SquadDailyRiskView.as_view()),
    path('simulator/assess', PlayerRiskSimulatorView.as_view()),
    path('absence/predict', AbsencePredictionView.as_view()),
    path('ai/explain', ExplainWithAIView.as_view()),
    path('ml/health', PhysioMLHealthView.as_view()),
    path('similarity/seed', SimilaritySeedView.as_view()),
    path('players/profiles', PhysioPlayersProfileView.as_view()),
]
