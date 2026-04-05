"""
Tests for the Scout app: Player and Contract CRUD,
and intentional removal of ScoutAI shortlist/similarity endpoints.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from scout.models import Player, Contract


def make_player(full_name="Test Player", position="CM", age=24,
                height_cm=180, weight_kg=75):
    return Player.objects.create(
        full_name=full_name, position=position, age=age,
        height_cm=height_cm, weight_kg=weight_kg,
    )


def authenticate_client(client: APIClient, username: str):
    User = get_user_model()
    user = User.objects.create_user(username=username, password='testpass123', role='admin')
    client.force_authenticate(user=user)
    return user


class TestPlayerCRUD(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = authenticate_client(self.client, 'admin_test_playercrud')

    def test_list_players_empty(self):
        res = self.client.get('/api/scout/players/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        results = data if isinstance(data, list) else data.get('results', [])
        self.assertEqual(len(results), 0)

    def test_create_player(self):
        payload = {
            'full_name': 'Karim Benzema', 'position': 'FW',
            'age': 35, 'height_cm': 185, 'weight_kg': 81,
        }
        res = self.client.post('/api/scout/players/', payload, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()['full_name'], 'Karim Benzema')
        self.assertEqual(Player.objects.count(), 1)

    def test_create_player_missing_name(self):
        res = self.client.post('/api/scout/players/', {'position': 'CM'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_retrieve_player(self):
        p = make_player('Lamine Yamal', 'FW', 16)
        res = self.client.get(f'/api/scout/players/{p.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['full_name'], 'Lamine Yamal')

    def test_update_player_age(self):
        p = make_player()
        res = self.client.patch(f'/api/scout/players/{p.id}/', {'age': 25}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['age'], 25)

    def test_delete_player(self):
        p = make_player()
        res = self.client.delete(f'/api/scout/players/{p.id}/')
        self.assertEqual(res.status_code, 204)
        self.assertEqual(Player.objects.count(), 0)

    def test_list_multiple_players(self):
        for i in range(5):
            make_player(f'Player {i}', age=20 + i)
        res = self.client.get('/api/scout/players/')
        data = res.json()
        results = data if isinstance(data, list) else data.get('results', [])
        self.assertEqual(len(results), 5)


class TestContractCRUD(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = authenticate_client(self.client, 'admin_test_contractcrud')
        self.player = make_player()

    def test_create_contract(self):
        payload = {
            'player': self.player.id,
            'salary_yearly': 1_000_000,
            'transfer_fee': 5_000_000,
            'start_date': '2024-01-01',
            'end_date': '2026-06-30',
        }
        res = self.client.post('/api/scout/contracts/', payload, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Contract.objects.count(), 1)

    def test_list_contracts(self):
        Contract.objects.create(player=self.player, salary_yearly=500_000)
        res = self.client.get('/api/scout/contracts/')
        data = res.json()
        results = data if isinstance(data, list) else data.get('results', [])
        self.assertGreaterEqual(len(results), 1)


class TestRemovedScoutAiEndpoints(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = authenticate_client(self.client, 'admin_test_removed_scoutai')

    def test_shortlist_endpoint_removed(self):
        res = self.client.get('/api/scout/shortlist/')
        self.assertEqual(res.status_code, 404)

    def test_similar_endpoint_removed(self):
        p = make_player('Removed Endpoint Probe', 'CM', 23)
        res = self.client.get(f'/api/scout/similar/{p.id}/')
        self.assertEqual(res.status_code, 404)
