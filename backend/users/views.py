from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import User
from .serializers import UserSerializer, RegisterSerializer, SmartClubTokenObtainPairSerializer


class SmartClubTokenObtainPairView(TokenObtainPairView):
    serializer_class = SmartClubTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    """Self-registration — admins only in production."""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class UserListView(generics.ListAPIView):
    """Admin-only user list."""
    queryset = User.objects.all().order_by('username')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]
