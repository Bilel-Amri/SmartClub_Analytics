from django.db import models
from django.conf import settings
from scout.models import Player


SEVERITY_CHOICES = [
    ('mild', 'Mild'),
    ('moderate', 'Moderate'),
    ('severe', 'Severe'),
]

RISK_BAND_CHOICES = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
]

CONFIDENCE_CHOICES = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
]


# ── Global (SoccerMon) models ─────────────────────────────────────────────────

class GlobalPlayer(models.Model):
    external_id = models.CharField(max_length=120, unique=True)  # "TeamA-<uuid>"
    team = models.CharField(max_length=20)                        # TeamA | TeamB

    def __str__(self):
        return self.external_id

    class Meta:
        ordering = ['team', 'external_id']


class GlobalDailyRecord(models.Model):
    player = models.ForeignKey(GlobalPlayer, on_delete=models.CASCADE,
                               related_name='daily_records')
    date = models.DateField()

    # Training load (pre-computed by SoccerMon)
    acwr        = models.FloatField(null=True, blank=True)
    atl         = models.FloatField(null=True, blank=True)
    ctl28       = models.FloatField(null=True, blank=True)
    ctl42       = models.FloatField(null=True, blank=True)
    daily_load  = models.FloatField(null=True, blank=True)
    monotony    = models.FloatField(null=True, blank=True)
    strain      = models.FloatField(null=True, blank=True)
    weekly_load = models.FloatField(null=True, blank=True)

    # Wellness (1–10 scales)
    fatigue        = models.FloatField(null=True, blank=True)
    mood           = models.FloatField(null=True, blank=True)
    readiness      = models.FloatField(null=True, blank=True)
    sleep_duration = models.FloatField(null=True, blank=True)
    sleep_quality  = models.FloatField(null=True, blank=True)
    soreness       = models.FloatField(null=True, blank=True)
    stress         = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('player', 'date')
        ordering = ['player', 'date']

    def __str__(self):
        return f'{self.player.external_id} @ {self.date}'


class GlobalInjuryEvent(models.Model):
    player       = models.ForeignKey(GlobalPlayer, on_delete=models.CASCADE,
                                     related_name='injury_events')
    injury_start = models.DateField()
    body_part    = models.CharField(max_length=60, default='unknown')
    severity     = models.CharField(max_length=20, default='minor')

    class Meta:
        ordering = ['player', 'injury_start']

    def __str__(self):
        return f'{self.player.external_id} – {self.body_part} @ {self.injury_start}'


class Injury(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='injuries')
    injury_type = models.CharField(max_length=100)
    date = models.DateField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='mild')
    days_absent = models.PositiveIntegerField(default=0)
    matches_missed = models.PositiveIntegerField(default=0)
    recurrence_flag = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f'{self.player.full_name} – {self.injury_type} ({self.date})'


class TrainingLoad(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='training_loads')
    date = models.DateField()
    total_distance_km = models.FloatField(default=0.0)
    sprints = models.IntegerField(default=0)
    accelerations = models.IntegerField(default=0)
    rpe = models.FloatField(null=True, blank=True, help_text='Rate of Perceived Exertion 1-10')
    sleep_quality = models.FloatField(null=True, blank=True, help_text='Sleep quality 1-10')
    soreness = models.FloatField(null=True, blank=True, help_text='Muscle Soreness 1-10')
    readiness = models.FloatField(null=True, blank=True, help_text='Readiness 1-10')
    minutes_played = models.IntegerField(default=0)

    def __str__(self) -> str:
        return f'{self.player.full_name} load {self.date}'


class InjuryRiskPrediction(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='risk_predictions')
    predicted_at = models.DateTimeField(auto_now_add=True)
    horizon_days = models.IntegerField(default=7)
    risk_probability = models.FloatField()
    risk_band = models.CharField(max_length=10, choices=RISK_BAND_CHOICES, default='low')
    confidence_band = models.CharField(max_length=10, choices=CONFIDENCE_CHOICES, default='medium')
    shap_factors = models.JSONField(default=list)
    recommended_action = models.TextField(blank=True, default='')
    monitoring_note = models.TextField(blank=True, default='')
    flag_for_physio_review = models.BooleanField(default=False)
    sufficient_history = models.BooleanField(default=True)
    data_quality_score = models.FloatField(default=1.0)
    top_factor = models.CharField(max_length=100, blank=True, default='')
    model_version = models.CharField(max_length=50, blank=True, default='')

    def __str__(self) -> str:
        return f'Risk({self.player.full_name}, {self.risk_probability:.2f}, {self.risk_band})'


class FlagAcknowledgment(models.Model):
    """Tracks when physio/admin has reviewed and acknowledged a high-risk flag."""
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='flag_acknowledgments')
    flagged_date = models.DateField(auto_now_add=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='acknowledged_flags'
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, default='')
    is_resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ['-flagged_date']

    def __str__(self) -> str:
        return f'Flag({self.player.full_name}, resolved={self.is_resolved})'


class AuditLog(models.Model):
    """Immutable audit trail for sensitive physiotherapy operations."""
    ACTION_CHOICES = [
        ('injury_created', 'Injury Created'),
        ('injury_updated', 'Injury Updated'),
        ('injury_deleted', 'Injury Deleted'),
        ('load_created', 'Training Load Created'),
        ('load_deleted', 'Training Load Deleted'),
        ('prediction_requested', 'Prediction Requested'),
        ('flag_acknowledged', 'Flag Acknowledged'),
        ('csv_import', 'CSV Import'),
        ('simulation_run', 'Simulation Run'),      # GDPR: log all what-if sims
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='physio_audit_logs'
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=40, blank=True, default='')
    resource_id = models.IntegerField(null=True, blank=True)
    detail = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'Audit({self.action}, {self.user}, {self.created_at:%Y-%m-%d})'


# ── PhysioAI v2 (three-function architecture) ───────────────────────────────

LOAD_BAND_CHOICES = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
]

FUNCTION_TYPE_CHOICES = [
    ('squad_daily_risk', 'Squad Daily Risk'),
    ('player_risk_simulator', 'Player Risk Simulator'),
    ('absence_prediction', 'Absence Prediction'),
]


class PhysioHistoricalCase(models.Model):
    player_name = models.CharField(max_length=120)
    age = models.PositiveSmallIntegerField()
    position = models.CharField(max_length=60)
    injury_type = models.CharField(max_length=80)
    primary_zone = models.CharField(max_length=80)
    context = models.CharField(max_length=80, default='training')
    previous_injuries = models.PositiveSmallIntegerField(default=0)
    previous_same_zone = models.PositiveSmallIntegerField(default=0)
    recurrence_same_zone = models.BooleanField(default=False)
    training_load_band = models.CharField(max_length=10, choices=LOAD_BAND_CHOICES, default='medium')
    days_since_last_intense = models.PositiveSmallIntegerField(default=2)
    absence_days = models.PositiveSmallIntegerField(default=0)
    risk_score = models.PositiveSmallIntegerField(default=0)
    outcome_label = models.CharField(max_length=20, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class PhysioSquadSnapshot(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='physio_squad_snapshots')
    snapshot_date = models.DateField()
    risk_score = models.PositiveSmallIntegerField(default=0)
    risk_band = models.CharField(max_length=10, choices=RISK_BAND_CHOICES, default='low')
    previous_injuries = models.PositiveSmallIntegerField(default=0)
    primary_zone = models.CharField(max_length=80, blank=True, default='')
    training_load_band = models.CharField(max_length=10, choices=LOAD_BAND_CHOICES, default='medium')
    days_since_last_intense = models.PositiveSmallIntegerField(default=2)
    top_drivers = models.JSONField(default=list, blank=True)
    actions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-snapshot_date', '-risk_score']
        unique_together = ('player', 'snapshot_date')


class PhysioRiskSimulationRun(models.Model):
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    player = models.ForeignKey(Player, null=True, blank=True, on_delete=models.SET_NULL)
    age = models.PositiveSmallIntegerField()
    position = models.CharField(max_length=60)
    previous_injuries = models.PositiveSmallIntegerField(default=0)
    injuries_last_2_seasons = models.PositiveSmallIntegerField(default=0)
    primary_zone = models.CharField(max_length=80)
    training_load_band = models.CharField(max_length=10, choices=LOAD_BAND_CHOICES, default='medium')
    days_since_last_intense = models.PositiveSmallIntegerField(default=2)
    risk_score = models.PositiveSmallIntegerField(default=0)
    risk_band = models.CharField(max_length=10, choices=RISK_BAND_CHOICES, default='low')
    risk_drivers = models.JSONField(default=list, blank=True)
    recommendation_blocks = models.JSONField(default=dict, blank=True)
    similar_profiles_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class PhysioAbsencePredictionRun(models.Model):
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    player = models.ForeignKey(Player, null=True, blank=True, on_delete=models.SET_NULL)
    player_name = models.CharField(max_length=120, blank=True, default='')
    age = models.PositiveSmallIntegerField(default=25)
    position = models.CharField(max_length=60, blank=True, default='')
    injury_type = models.CharField(max_length=80)
    context = models.CharField(max_length=80, default='training session')
    previous_same_zone = models.PositiveSmallIntegerField(default=0)
    recurrence_same_zone = models.BooleanField(default=False)
    severity_score = models.FloatField(default=0.0)
    severity_class = models.CharField(max_length=20, blank=True, default='')
    confidence_band = models.CharField(max_length=10, choices=CONFIDENCE_CHOICES, default='medium')
    absence_days_min = models.PositiveSmallIntegerField(default=0)
    absence_days_max = models.PositiveSmallIntegerField(default=0)
    absence_weeks_label = models.CharField(max_length=30, blank=True, default='')
    immediate_actions = models.JSONField(default=dict, blank=True)
    similar_cases_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class PhysioSimilarityMatch(models.Model):
    function_type = models.CharField(max_length=30, choices=FUNCTION_TYPE_CHOICES)
    simulation_run = models.ForeignKey(PhysioRiskSimulationRun, null=True, blank=True, on_delete=models.CASCADE, related_name='matches')
    absence_run = models.ForeignKey(PhysioAbsencePredictionRun, null=True, blank=True, on_delete=models.CASCADE, related_name='matches')
    case = models.ForeignKey(PhysioHistoricalCase, on_delete=models.CASCADE, related_name='matched_in')
    rank = models.PositiveSmallIntegerField(default=1)
    distance = models.FloatField(default=0.0)
    match_pct = models.FloatField(default=0.0)
    summary = models.CharField(max_length=300, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['rank']


class PhysioAIExplanation(models.Model):
    function_type = models.CharField(max_length=30, choices=FUNCTION_TYPE_CHOICES)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    simulation_run = models.ForeignKey(PhysioRiskSimulationRun, null=True, blank=True, on_delete=models.SET_NULL)
    absence_run = models.ForeignKey(PhysioAbsencePredictionRun, null=True, blank=True, on_delete=models.SET_NULL)
    request_payload = models.JSONField(default=dict, blank=True)
    response_text = models.TextField(blank=True, default='')
    provider = models.CharField(max_length=30, default='fallback')
    fallback_used = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
