"""
Tests for legacy /api/physio/global/* compatibility endpoints.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from physio.models import GlobalDailyRecord, GlobalInjuryEvent, GlobalPlayer


def make_player(external_id='TeamA-p1', team='TeamA'):
    return GlobalPlayer.objects.create(external_id=external_id, team=team)


def make_records(player, n=10, start='2024-01-01'):
    base = datetime.date.fromisoformat(start)
    rows = []
    for i in range(n):
        rows.append(
            GlobalDailyRecord(
                player=player,
                date=base + datetime.timedelta(days=i),
                acwr=1.0 + i * 0.01,
                daily_load=320 + i,
                soreness=2 + (i % 3),
                readiness=4,
            )
        )
    GlobalDailyRecord.objects.bulk_create(rows)


class AuthenticatedGlobalAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            username=f'admin_{self.__class__.__name__.lower()}',
            password='testpass123',
            role='admin',
        )
        self.client.force_authenticate(user=self.user)


class TestGlobalSummaryView(AuthenticatedGlobalAPITestCase):
    def test_empty_summary(self):
        res = self.client.get('/api/physio/global/summary')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['players'], 0)
        self.assertEqual(data['daily_records'], 0)
        self.assertEqual(data['injury_events'], 0)
        self.assertIn('model_7d', data)

    def test_summary_counts(self):
        p = make_player('TeamA-s1', 'TeamA')
        make_records(p, n=4)
        GlobalInjuryEvent.objects.create(
            player=p,
            injury_start=datetime.date(2024, 1, 3),
            body_part='Hamstring',
            severity='moderate',
        )

        res = self.client.get('/api/physio/global/summary')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['players'], 1)
        self.assertEqual(data['daily_records'], 4)
        self.assertEqual(data['injury_events'], 1)


class TestGlobalPlayersView(AuthenticatedGlobalAPITestCase):
    def test_players_are_listed_and_ordered(self):
        make_player('TeamB-b2', 'TeamB')
        make_player('TeamA-a2', 'TeamA')
        make_player('TeamA-a1', 'TeamA')

        res = self.client.get('/api/physio/global/players')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 3)
        self.assertEqual(data[0]['team'], 'TeamA')
        self.assertEqual(data[0]['external_id'], 'TeamA-a1')
        self.assertEqual(data[1]['external_id'], 'TeamA-a2')
        self.assertEqual(data[2]['team'], 'TeamB')


class TestGlobalMetricsView(AuthenticatedGlobalAPITestCase):
    def test_metrics_payload_shape(self):
        p = make_player('TeamA-m1', 'TeamA')
        make_records(p, n=3)

        res = self.client.get('/api/physio/global/metrics')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('players', data)
        self.assertIn('daily_records', data)
        self.assertIn('injury_events', data)
        self.assertIn('last_record_date', data)


class TestGlobalRiskAndShapViews(AuthenticatedGlobalAPITestCase):
    def setUp(self):
        super().setUp()
        self.player = make_player('TeamA-risk1', 'TeamA')
        make_records(self.player, n=6)

    def test_risk_returns_integration_shell_response(self):
        res = self.client.get(f'/api/physio/global/risk/{self.player.id}/')
        self.assertEqual(res.status_code, 503)
        data = res.json()
        self.assertIn('detail', data)
        self.assertIn('integration', data)

    def test_shap_returns_integration_shell_response(self):
        res = self.client.get(f'/api/physio/global/shap/{self.player.id}/')
        self.assertEqual(res.status_code, 503)
        data = res.json()
        self.assertIn('detail', data)
        self.assertIn('integration', data)


class TestGlobalTimeSeriesView(AuthenticatedGlobalAPITestCase):
    def setUp(self):
        super().setUp()
        self.player = make_player('TeamA-ts1', 'TeamA')
        make_records(self.player, n=12)
        GlobalInjuryEvent.objects.create(
            player=self.player,
            injury_start=datetime.date(2024, 1, 5),
            body_part='Ankle',
            severity='minor',
        )

    def test_timeseries_default_shape(self):
        res = self.client.get(f'/api/physio/global/timeseries/{self.player.id}/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['player_id'], self.player.id)
        self.assertIn('series', data)
        self.assertIn('metrics', data)
        self.assertTrue(len(data['series']) > 0)
        self.assertIn('date', data['series'][0])
        self.assertIn('injury', data['series'][0])

    def test_timeseries_respects_limit(self):
        res = self.client.get(
            f'/api/physio/global/timeseries/{self.player.id}/',
            {'limit': 5},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertLessEqual(len(data['series']), 5)

    def test_timeseries_unknown_player_returns_empty_series(self):
        res = self.client.get('/api/physio/global/timeseries/999999/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['player_id'], 999999)
        self.assertEqual(data['series'], [])
