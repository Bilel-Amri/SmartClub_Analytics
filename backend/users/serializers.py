from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from .models import User


class SmartClubTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds role to JWT payload so frontend can gate views."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['full_name'] = f"{user.first_name} {user.last_name}".strip() or user.username
        return token


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role']
        read_only_fields = ['id']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name', 'role']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
