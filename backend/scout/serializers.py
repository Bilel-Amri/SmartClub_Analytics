from rest_framework import serializers
from .models import Player, Contract


class ContractInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ['id', 'salary_yearly', 'transfer_fee', 'start_date', 'end_date']


class PlayerSerializer(serializers.ModelSerializer):
    contract = ContractInlineSerializer(read_only=True)

    class Meta:
        model = Player
        fields = ['id', 'full_name', 'position', 'age', 'height_cm',
                  'weight_kg', 'preferred_foot', 'created_at', 'contract']


class ContractSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source='player.full_name', read_only=True)

    class Meta:
        model = Contract
        fields = '__all__'