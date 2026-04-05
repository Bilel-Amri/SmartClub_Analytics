from django.db import models


POSITION_CHOICES = [
    ('GK', 'Goalkeeper'),
    ('CB', 'Centre Back'),
    ('LB', 'Left Back'),
    ('RB', 'Right Back'),
    ('CDM', 'Defensive Midfielder'),
    ('CM', 'Central Midfielder'),
    ('CAM', 'Attacking Midfielder'),
    ('LW', 'Left Wing'),
    ('RW', 'Right Wing'),
    ('FW', 'Forward'),
]


class Player(models.Model):
    full_name = models.CharField(max_length=150)
    position = models.CharField(max_length=10, choices=POSITION_CHOICES, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    height_cm = models.FloatField(null=True, blank=True)
    weight_kg = models.FloatField(null=True, blank=True)
    preferred_foot = models.CharField(max_length=10, blank=True)
    nationality = models.CharField(max_length=80, blank=True, default='')
    current_club = models.CharField(max_length=100, blank=True, default='')
    market_value_eur = models.FloatField(null=True, blank=True, default=0)
    phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.full_name


class Contract(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE, related_name='contract')
    salary_yearly = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                        help_text='Yearly salary in EUR')
    transfer_fee = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                       help_text='Transfer fee in EUR')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def __str__(self) -> str:
        return f'Contract({self.player.full_name})'


class PlayerMatchStats(models.Model):
    """Per-player aggregated match features used for embeddings."""
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='match_stats')
    season = models.CharField(max_length=10, default='2024-25')
    progressive_passes = models.FloatField(default=0)
    carries = models.FloatField(default=0)
    defensive_actions = models.FloatField(default=0)
    duel_win_rate = models.FloatField(default=0)
    crosses = models.FloatField(default=0)
    xg_proxy = models.FloatField(default=0)
    xa_proxy = models.FloatField(default=0)

    class Meta:
        unique_together = ('player', 'season')


class PlayerEmbedding(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE, related_name='embedding')
    vector = models.JSONField(default=list)  # list of floats
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f'Embedding({self.player.full_name})'