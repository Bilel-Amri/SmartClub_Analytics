from django.urls import path

from .views import InjuriesSummaryView, ModelPerformanceView, RiskPredictView

urlpatterns = [
    path('injuries/summary', InjuriesSummaryView.as_view()),
    path('risk/predict', RiskPredictView.as_view()),
    path('model-performance', ModelPerformanceView.as_view()),
]
