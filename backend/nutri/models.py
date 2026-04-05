from django.db import models
from scout.models import Player


DAY_TYPE_CHOICES = [('match', 'Match'), ('training', 'Training'), ('rest', 'Rest')]
GOAL_CHOICES     = [('maintain', 'Maintain'), ('bulk', 'Bulk'), ('cut', 'Cut')]
SOURCE_CHOICES   = [('manual', 'Manual'), ('usda', 'USDA')]
MEAL_TIME_CHOICES = [
    ('breakfast', 'Breakfast'),
    ('am_snack',  'AM Snack'),
    ('lunch',     'Lunch'),
    ('pm_snack',  'PM Snack'),
    ('dinner',    'Dinner'),
    ('pre_train', 'Pre-Training'),
    ('post_train','Post-Training'),
    ('pre_sleep', 'Pre-Sleep'),
]
SUPP_TIMING_CHOICES = [
    ('pre_train',  'Pre-Training'),
    ('intra_train','Intra-Training'),
    ('post_train', 'Post-Training'),
    ('morning',    'Morning'),
    ('evening',    'Evening'),
    ('with_meal',  'With Meal'),
]


class Food(models.Model):
    name = models.CharField(max_length=150, unique=True)
    calories_100g = models.FloatField(help_text='kcal per 100 g')
    protein_100g = models.FloatField(help_text='g per 100 g')
    carbs_100g = models.FloatField(help_text='g per 100 g')
    fat_100g = models.FloatField(help_text='g per 100 g')
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='manual')
    fdc_id = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self) -> str:
        return self.name


class DailyPlan(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='nutrition_plans')
    date = models.DateField()
    day_type = models.CharField(max_length=10, choices=DAY_TYPE_CHOICES, default='training')
    goal = models.CharField(max_length=10, choices=GOAL_CHOICES, default='maintain')
    calories = models.FloatField()
    protein_g = models.FloatField()
    carbs_g = models.FloatField()
    fat_g = models.FloatField()
    notes = models.TextField(blank=True)

    def __str__(self) -> str:
        return f'{self.player.full_name} – {self.date}({self.day_type})'


class MealLog(models.Model):
    """
    A single food entry logged against a DailyPlan meal slot.
    Enables 'Target vs Actual' ring chart comparison in NutriAI.
    """
    plan      = models.ForeignKey(DailyPlan, on_delete=models.CASCADE, related_name='meal_logs')
    food      = models.ForeignKey(Food, on_delete=models.CASCADE, related_name='meal_logs')
    grams     = models.FloatField()
    meal_time = models.CharField(max_length=20, choices=MEAL_TIME_CHOICES, default='breakfast')
    logged_at = models.DateTimeField(auto_now_add=True)

    # Computed macros (stored for fast retrieval — computed on save in the view)
    calories  = models.FloatField(default=0.0)
    protein_g = models.FloatField(default=0.0)
    carbs_g   = models.FloatField(default=0.0)
    fat_g     = models.FloatField(default=0.0)

    class Meta:
        ordering = ['meal_time', 'logged_at']

    def __str__(self) -> str:
        return f'{self.plan} | {self.meal_time}: {self.grams}g {self.food}'

    def save(self, *args, **kwargs) -> None:  # type: ignore[override]
        factor        = self.grams / 100.0
        self.calories = round(self.food.calories_100g * factor, 1)
        self.protein_g = round(self.food.protein_100g  * factor, 1)
        self.carbs_g   = round(self.food.carbs_100g    * factor, 1)
        self.fat_g     = round(self.food.fat_100g      * factor, 1)
        super().save(*args, **kwargs)


class Supplement(models.Model):
    """
    Individual supplement entry for a player.

    Anti-doping compliance fields
    -----------------------------
    batch_tested  : bool — whether the product holds Informed Sport / BSCG certification
    batch_number  : str  — lot/batch number for forensic audit trail
    cert_body     : str  — certifying organisation (Informed Sport, BSCG, NSF, etc.)
    """
    player       = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='supplements')
    date         = models.DateField()
    name         = models.CharField(max_length=120, help_text='Supplement product name')
    dose_mg      = models.FloatField(help_text='Dose in mg (or g × 1000 for convenience)')
    timing       = models.CharField(max_length=20, choices=SUPP_TIMING_CHOICES, default='post_train')

    # Anti-doping fields (WADA/IOC compliance)
    batch_tested = models.BooleanField(
        default=False,
        help_text='Product certified by Informed Sport, BSCG, or NSF for anti-doping compliance',
    )
    batch_number = models.CharField(
        max_length=80, blank=True, default='',
        help_text='Lot / batch number — required for forensic audit in doping investigations',
    )
    cert_body    = models.CharField(
        max_length=80, blank=True, default='',
        help_text='Certifying body: Informed Sport | BSCG | NSF | Informed Choice | None',
    )
    notes        = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-date', 'name']

    def __str__(self) -> str:
        certified = '✓' if self.batch_tested else '⚠'
        return f'{certified} {self.player.full_name} | {self.name} {self.dose_mg}mg ({self.date})'