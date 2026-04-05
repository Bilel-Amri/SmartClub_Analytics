from django.urls import path
from .views import (PlayerListCreateView, PlayerDetailView,
                   ContractListCreateView, ContractDetailView)

urlpatterns = [
    path('players/', PlayerListCreateView.as_view()),
    path('players/<int:pk>/', PlayerDetailView.as_view()),
    path('contracts/', ContractListCreateView.as_view()),
    path('contracts/<int:pk>/', ContractDetailView.as_view()),
]