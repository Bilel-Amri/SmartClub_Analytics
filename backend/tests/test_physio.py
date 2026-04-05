"""
Tests for the Physio app: Injury and TrainingLoad CRUD,
InjuryRisk endpoint, DurationPredict endpoint.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from scout.models import Player
from physio.models import Injury, TrainingLoad


def make_player(name="Physio Player", position="CM"):
    return Player.objects.create(full_name=name, position=position, age=24)


class AuthenticatedAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            username=f'admin_{self.__class__.__name__.lower()}',
            password='testpass123',
            role='admin',
        )
        self.client.force_authenticate(user=self.user)


class TestInjuryCRUD(AuthenticatedAPITestCase):
    def setUp(self):
        super().setUp()
        self.player = make_player()

    def test_create_injury(self):
        payload = {
            'player': self.player.id,
            'injury_type': 'Hamstring',
            'date': '2024-03-15',
            'severity': 'moderate',
            'days_absent': 14,
            'matches_missed': 3,
        }
        res = self.client.post('/api/physio/injuries/', payload, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Injury.objects.count(), 1)

    def test_list_injuries(self):
        Injury.objects.create(
            player=self.player, injury_type='Knee', date='2024-01-10',
            severity='mild', days_absent=7, matches_missed=1
        )
        res = self.client.get('/api/physio/injuries/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        results = data if isinstance(data, list) else data.get('results', [])
        self.assertGreaterEqual(len(results), 1)

    def test_injury_severity_choices(self):
        """Only mild/moderate/severe accepted."""
        payload = {
            'player': self.player.id,
            'injury_type': 'Ankle',
            'date': '2024-04-01',
            'severity': 'critical',  # invalid
            'days_absent': 30,
        }
        res = self.client.post('/api/physio/injuries/', payload, format='json')
        self.assertEqual(res.status_code, 400)

    def test_retrieve_injury(self):
        inj = Injury.objects.create(
            player=self.player, injury_type='Back', date='2024-02-10',
            severity='severe', days_absent=45
        )
        res = self.client.get(f'/api/physio/injuries/{inj.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['injury_type'], 'Back')

    def test_delete_injury(self):
        inj = Injury.objects.create(
            player=self.player, injury_type='Groin', date='2024-03-01',
            severity='mild', days_absent=5
        )
        res = self.client.delete(f'/api/physio/injuries/{inj.id}/')
        self.assertEqual(res.status_code, 204)


class TestTrainingLoad(AuthenticatedAPITestCase):
    def setUp(self):
        super().setUp()
        self.player = make_player('Load Player')

    def test_create_load(self):
        payload = {
            'player': self.player.id,
            'date': '2024-04-10',
            'total_distance_km': 10.5,
            'sprints': 28,
            'accelerations': 40,
            'rpe': 7.0,
            'sleep_quality': 7.5,
            'minutes_played': 90,
        }
        res = self.client.post('/api/physio/training-loads/', payload, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(TrainingLoad.objects.count(), 1)

    def test_list_loads(self):
        TrainingLoad.objects.create(
            player=self.player, date='2024-04-10',
            total_distance_km=8.0, rpe=6.0
        )
        res = self.client.get('/api/physio/training-loads/')
        self.assertEqual(res.status_code, 200)


class TestInjuryRisk(AuthenticatedAPITestCase):
    def setUp(self):
        super().setUp()
        self.player = make_player('Risk Player')
        # Create some loads for the rule-based fallback
        for i in range(5):
            TrainingLoad.objects.create(
                player=self.player,
                date=f'2024-04-{10 + i:02d}',
                total_distance_km=10.0 + i,
                sprints=25 + i,
                accelerations=35,
                rpe=7.5,
                sleep_quality=6.0,
            )
        Injury.objects.create(
            player=self.player, injury_type='Hamstring',
            date='2024-03-01', severity='moderate',
            days_absent=14
        )

    def test_injury_risk_response(self):
        res = self.client.get(f'/api/physio/injury-risk/{self.player.id}/')
        self.assertIn(res.status_code, [200, 503])
        data = res.json()
        if res.status_code == 200:
            self.assertIn('risk_probability', data)
            self.assertGreaterEqual(data['risk_probability'], 0.0)
            self.assertLessEqual(data['risk_probability'], 1.0)
        else:
            self.assertIn('detail', data)
            self.assertIn('integration', data)

    def test_injury_risk_horizon_30(self):
        res = self.client.get(
            f'/api/physio/injury-risk/{self.player.id}/',
            {'horizon_days': 30}
        )
        self.assertIn(res.status_code, [200, 503])

    def test_injury_risk_no_data_player(self):
        """Player with no loads should still return a valid response."""
        p = make_player('Empty Player')
        res = self.client.get(f'/api/physio/injury-risk/{p.id}/')
        self.assertIn(res.status_code, [200, 404, 503])

    def test_duration_predict(self):
        inj = Injury.objects.create(
            player=self.player, injury_type='Knee',
            date='2024-04-15', severity='moderate', days_absent=18
        )
        res = self.client.get(f'/api/physio/duration-predict/{inj.id}/')
        self.assertIn(res.status_code, [200, 503])
        data = res.json()
        if res.status_code == 200:
            self.assertIn('predicted_days', data)
            self.assertGreater(data['predicted_days'], 0)
        else:
            self.assertIn('detail', data)
            self.assertIn('integration', data)

    def test_duration_predict_severe_recurrence(self):
        inj = Injury.objects.create(
            player=self.player, injury_type='Hamstring',
            date='2024-05-01', severity='severe',
            days_absent=45, recurrence_flag=True
        )
        res = self.client.get(f'/api/physio/duration-predict/{inj.id}/')
        self.assertIn(res.status_code, [200, 503])
        data = res.json()
        if res.status_code == 200:
            # severe + recurrence should not reduce baseline estimate.
            self.assertGreaterEqual(data['predicted_days'], 45)
        else:
            self.assertIn('detail', data)
            self.assertIn('integration', data)
