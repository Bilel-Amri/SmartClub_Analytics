from rest_framework import serializers
from .models import Injury, TrainingLoad, InjuryRiskPrediction, AuditLog, FlagAcknowledgment


class InjurySerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source='player.full_name', read_only=True)

    class Meta:
        model = Injury
        fields = '__all__'


class TrainingLoadSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source='player.full_name', read_only=True)

    class Meta:
        model = TrainingLoad
        fields = '__all__'


class InjuryRiskPredictionSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source='player.full_name', read_only=True)

    class Meta:
        model = InjuryRiskPrediction
        fields = '__all__'


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = AuditLog
        fields = '__all__'


class FlagAcknowledgmentSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source='player.full_name', read_only=True)
    acknowledged_by_name = serializers.CharField(source='acknowledged_by.username', read_only=True)

    class Meta:
        model = FlagAcknowledgment
        fields = '__all__'