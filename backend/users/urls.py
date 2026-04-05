from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import SmartClubTokenObtainPairView, RegisterView, MeView, UserListView

urlpatterns = [
    path('token/', SmartClubTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterView.as_view(), name='register'),
    path('me/', MeView.as_view(), name='me'),
    path('users/', UserListView.as_view(), name='user_list'),
]
