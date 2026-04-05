"""
Tests for the chat endpoint backed by ORM (no HTTP self-calls).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from nutri.models import DailyPlan
from physio.models import Injury, InjuryRiskPrediction, TrainingLoad
from scout.models import Player


def make_player(name='Test Player', position='FW'):
    return Player.objects.create(
        full_name=name,
        position=position,
        age=24,
        weight_kg=75,
        height_cm=180,
    )


class TestChatbot(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            username='admin_test_chatbot',
            password='testpass123',
            role='admin',
        )
        self.client.force_authenticate(user=self.user)
        self.player = make_player()

    def test_chat_endpoint_exists(self):
        res = self.client.post('/api/chat/', {'message': 'hello'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertIn('reply', res.json())

    def test_chat_missing_message(self):
        res = self.client.post('/api/chat/', {}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_chat_returns_reply_for_players(self):
        res = self.client.post('/api/chat/', {'message': 'show all players'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertIn('reply', res.json())
        self.assertIn('Test Player', res.json()['reply'])

    def test_chat_injury_risk_query(self):
        InjuryRiskPrediction.objects.create(
            player=self.player,
            horizon_days=7,
            risk_probability=0.35,
            risk_band='medium',
            confidence_band='medium',
            shap_factors=[{'feature': 'fatigue', 'value': 0.4}],
            recommended_action='Monitor load',
            monitoring_note='Watch fatigue trend',
            top_factor='fatigue',
            model_version='test',
        )
        res = self.client.post(
            '/api/chat/',
            {'message': 'injury risk for Test Player'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn('Injury risk for Test Player', res.json()['reply'])

    def test_chat_nutri_query(self):
        DailyPlan.objects.create(
            player=self.player,
            date=datetime.date(2024, 4, 15),
            day_type='training',
            goal='maintain',
            calories=2800,
            protein_g=175,
            carbs_g=350,
            fat_g=78,
        )
        res = self.client.post(
            '/api/chat/',
            {'message': 'nutrition plan for Test Player'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn('Latest nutrition plan for Test Player', res.json()['reply'])

    def test_chat_injuries_query(self):
        Injury.objects.create(
            player=self.player,
            injury_type='Hamstring',
            date=datetime.date(2024, 3, 1),
            severity='mild',
            days_absent=7,
        )
        res = self.client.post(
            '/api/chat/',
            {'message': 'show recent injuries'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn('Recent injuries', res.json()['reply'])

    def test_chat_training_load_query(self):
        TrainingLoad.objects.create(
            player=self.player,
            date=datetime.date(2024, 4, 10),
            total_distance_km=9.4,
            rpe=7.0,
            sleep_quality=7.5,
        )
        res = self.client.post(
            '/api/chat/',
            {'message': 'training load for Test Player'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn('Recent training loads', res.json()['reply'])
