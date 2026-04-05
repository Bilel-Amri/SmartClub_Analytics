from django.urls import path
from .views import (
    InjuryListCreateView, InjuryDetailView,
    TrainingLoadListCreateView, TrainingLoadDetailView, QuickWellnessView,
    InjuryRiskView, DurationPredictView,
    InjuriesSummaryView, RiskPredictView,
    # Squad decision-support
    SquadOverviewTodayView, FlaggedPlayersView, AcknowledgeFlagView,
    ReturningPlayersView, PredictionHistoryView,
    # Admin / reporting
    ModelMetadataView, ModelPerformanceView, AuditLogListView,
    InjuryCSVImportView, LoadCSVImportView,
    # Global SoccerMon endpoints
    GlobalSummaryView, GlobalPlayersView, GlobalMetricsView,
    GlobalRiskView, GlobalSHAPView, GlobalTimeSeriesView,
    GlobalSquadOverviewView,
    # What-If simulator
    PhysioSimulationView,
)

urlpatterns = [
    # ── Club CRUD ─────────────────────────────────────────────────────────
    path('injuries/', InjuryListCreateView.as_view()),
    path('injuries/<int:pk>/', InjuryDetailView.as_view()),
    path('training-loads/', TrainingLoadListCreateView.as_view()),
    path('training-loads/<int:pk>/', TrainingLoadDetailView.as_view()),
    path('quick-wellness/', QuickWellnessView.as_view()),

    # ── Risk prediction ───────────────────────────────────────────────────
    path('injury-risk/<int:player_id>/', InjuryRiskView.as_view()),
    path('duration-predict/<int:injury_id>/', DurationPredictView.as_view()),
    path('injuries/summary', InjuriesSummaryView.as_view()),
    path('risk/predict', RiskPredictView.as_view()),

    # ── Squad decision-support ────────────────────────────────────────────
    path('overview/today', SquadOverviewTodayView.as_view()),
    path('flagged', FlaggedPlayersView.as_view()),
    path('returning', ReturningPlayersView.as_view()),
    path('acknowledge/<int:player_id>/', AcknowledgeFlagView.as_view()),
    path('player/<int:player_id>/predictions/', PredictionHistoryView.as_view()),

    # ── Reporting / admin ─────────────────────────────────────────────────
    path('model-metadata', ModelMetadataView.as_view()),
    path('model-performance', ModelPerformanceView.as_view()),
    path('audit-log/', AuditLogListView.as_view()),
    path('import/injuries/', InjuryCSVImportView.as_view()),
    path('import/loads/', LoadCSVImportView.as_view()),

    # ── What-If simulator ────────────────────────────────────────────────
    path('simulate/', PhysioSimulationView.as_view()),

    # ── Global SoccerMon ──────────────────────────────────────────────────
    path('global/summary', GlobalSummaryView.as_view()),
    path('global/players', GlobalPlayersView.as_view()),
    path('global/metrics', GlobalMetricsView.as_view()),
    path('global/risk/<int:player_id>/', GlobalRiskView.as_view()),
    path('global/shap/<int:player_id>/', GlobalSHAPView.as_view()),
    path('global/timeseries/<int:player_id>/', GlobalTimeSeriesView.as_view()),
    path('global/squad-overview', GlobalSquadOverviewView.as_view()),
]
