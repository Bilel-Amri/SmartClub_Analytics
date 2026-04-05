from rest_framework import generics
from .models import Player, Contract
from .serializers import PlayerSerializer, ContractSerializer


class PlayerListCreateView(generics.ListCreateAPIView):
    queryset = Player.objects.select_related('contract').prefetch_related('injuries', 'match_stats').order_by('id')
    serializer_class = PlayerSerializer


class PlayerDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer


class ContractListCreateView(generics.ListCreateAPIView):
    queryset = Contract.objects.select_related('player').all().order_by('id')
    serializer_class = ContractSerializer


class ContractDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer