from rest_framework import serializers
from .models import Food, DailyPlan, MealLog, Supplement


class FoodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Food
        fields = '__all__'


class DailyPlanSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source='player.full_name', read_only=True)

    class Meta:
        model = DailyPlan
        fields = '__all__'


class MealItemSerializer(serializers.Serializer):
    food_id = serializers.IntegerField(required=False, allow_null=True)
    food_name = serializers.CharField(required=False, allow_blank=True)
    # legacy alias
    name = serializers.CharField(required=False, allow_blank=True)
    grams = serializers.FloatField()


class MealCalcRequestSerializer(serializers.Serializer):
    items = MealItemSerializer(many=True)


class GeneratePlanRequestSerializer(serializers.Serializer):
    # Accept both 'player' (frontend) and 'player_id' (legacy)
    player = serializers.IntegerField(required=False, allow_null=True)
    player_id = serializers.IntegerField(required=False, allow_null=True)
    date = serializers.DateField()
    day_type = serializers.ChoiceField(choices=['match', 'training', 'rest'])
    goal = serializers.ChoiceField(choices=['maintain', 'bulk', 'cut'])
    # Optional biometric overrides (take priority over player model values)
    weight_kg = serializers.FloatField(required=False, allow_null=True)
    height_cm = serializers.FloatField(required=False, allow_null=True)
    age = serializers.IntegerField(required=False, allow_null=True)
    sex = serializers.ChoiceField(choices=['M', 'F'], default='M', required=False)

    def validate(self, attrs):
        if not attrs.get('player_id') and not attrs.get('player'):
            raise serializers.ValidationError('player or player_id is required.')
        attrs.setdefault('player_id', attrs.get('player'))
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
# Meal Log
# ─────────────────────────────────────────────────────────────────────────────

class MealLogSerializer(serializers.ModelSerializer):
    food_name  = serializers.CharField(source='food.name',  read_only=True)
    plan_date  = serializers.DateField(source='plan.date',  read_only=True)
    player_name = serializers.CharField(source='plan.player.full_name', read_only=True)

    class Meta:
        model  = MealLog
        fields = '__all__'
        read_only_fields = ('calories', 'protein_g', 'carbs_g', 'fat_g', 'logged_at')


class MealLogCreateSerializer(serializers.Serializer):
    """Lightweight write serializer — macro fields are computed from the food model."""
    plan      = serializers.IntegerField(help_text='DailyPlan pk')
    food      = serializers.IntegerField(help_text='Food pk')
    grams     = serializers.FloatField(min_value=1)
    meal_time = serializers.ChoiceField(
        choices=['breakfast', 'am_snack', 'lunch', 'pm_snack',
                 'dinner', 'pre_train', 'post_train', 'pre_sleep'],
        default='breakfast',
    )


# ─────────────────────────────────────────────────────────────────────────────
# Supplement
# ─────────────────────────────────────────────────────────────────────────────

class SupplementSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source='player.full_name', read_only=True)

    class Meta:
        model  = Supplement
        fields = '__all__'