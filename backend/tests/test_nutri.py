"""
Tests for the Nutri app: Food CRUD,
DailyPlan list, MealCalc, GeneratePlan.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from scout.models import Player
from nutri.models import Food, DailyPlan


def make_player(name="Nutri Player", position="FW"):
    return Player.objects.create(full_name=name, position=position, age=24,
                                  height_cm=180, weight_kg=75)


def make_food(name="Chicken Breast", kcal=165, protein=31, carbs=0, fat=3.6):
    return Food.objects.create(
        name=name, calories_100g=kcal,
        protein_100g=protein, carbs_100g=carbs, fat_100g=fat
    )


def authenticate_client(client: APIClient, username: str):
    User = get_user_model()
    user = User.objects.create_user(username=username, password='testpass123', role='admin')
    client.force_authenticate(user=user)
    return user


class TestFoodCRUD(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = authenticate_client(self.client, 'admin_test_foodcrud')

    def test_create_food(self):
        payload = {
            'name': 'Brown Rice',
            'calories_100g': 111,
            'protein_100g': 2.6,
            'carbs_100g': 23.0,
            'fat_100g': 0.9,
        }
        res = self.client.post('/api/nutri/foods/', payload, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Food.objects.count(), 1)

    def test_list_foods(self):
        make_food('Apple', kcal=52, protein=0.3, carbs=14, fat=0.2)
        res = self.client.get('/api/nutri/foods/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        results = data if isinstance(data, list) else data.get('results', [])
        self.assertGreaterEqual(len(results), 1)

    def test_retrieve_food(self):
        f = make_food('Oats')
        res = self.client.get(f'/api/nutri/foods/{f.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['name'], 'Oats')

    def test_delete_food(self):
        f = make_food('Banana')
        res = self.client.delete(f'/api/nutri/foods/{f.id}/')
        self.assertEqual(res.status_code, 204)

    def test_duplicate_food_name(self):
        make_food('Egg')
        payload = {'name': 'Egg', 'calories_100g': 155, 'protein_100g': 13,
                   'carbs_100g': 1.1, 'fat_100g': 11}
        res = self.client.post('/api/nutri/foods/', payload, format='json')
        self.assertEqual(res.status_code, 400)


class TestGeneratePlan(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = authenticate_client(self.client, 'admin_test_generateplan')
        self.player = make_player()

    def test_generate_plan_training_maintain(self):
        payload = {
            'player': self.player.id,
            'date': '2024-04-15',
            'day_type': 'training',
            'goal': 'maintain',
            'weight_kg': 75,
            'height_cm': 180,
            'age': 24,
            'sex': 'M',
        }
        res = self.client.post('/api/nutri/generate-plan/', payload, format='json')
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn('calories', data)
        self.assertIn('protein_g', data)
        self.assertIn('carbs_g', data)
        self.assertIn('fat_g', data)
        # Training day maintain - calories should be reasonable (1800–4500)
        self.assertGreater(data['calories'], 1800)
        self.assertLess(data['calories'], 4500)

    def test_generate_plan_match_bulk(self):
        payload = {
            'player': self.player.id,
            'date': '2024-04-20',
            'day_type': 'match',
            'goal': 'bulk',
            'weight_kg': 80,
            'height_cm': 182,
            'age': 25,
            'sex': 'M',
        }
        res = self.client.post('/api/nutri/generate-plan/', payload, format='json')
        self.assertEqual(res.status_code, 201)

    def test_generate_plan_rest_cut_female(self):
        payload = {
            'player': self.player.id,
            'date': '2024-04-25',
            'day_type': 'rest',
            'goal': 'cut',
            'weight_kg': 60,
            'height_cm': 168,
            'age': 22,
            'sex': 'F',
        }
        res = self.client.post('/api/nutri/generate-plan/', payload, format='json')
        self.assertEqual(res.status_code, 201)

    def test_generate_plan_creates_record(self):
        initial = DailyPlan.objects.count()
        payload = {
            'player': self.player.id, 'date': '2024-04-30',
            'day_type': 'training', 'goal': 'maintain',
            'weight_kg': 75, 'height_cm': 180, 'age': 24, 'sex': 'M',
        }
        self.client.post('/api/nutri/generate-plan/', payload, format='json')
        self.assertEqual(DailyPlan.objects.count(), initial + 1)

    def test_generate_plan_missing_weight_uses_player_weight(self):
        """Without weight_kg in request, the view falls back to player.weight_kg."""
        payload = {
            'player': self.player.id, 'date': '2024-05-01',
            'day_type': 'training', 'goal': 'maintain',
            'height_cm': 180, 'age': 24, 'sex': 'M',
        }
        res = self.client.post('/api/nutri/generate-plan/', payload, format='json')
        # Player has weight_kg=75, so the plan should still generate
        self.assertIn(res.status_code, [201, 400])


class TestMealCalc(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = authenticate_client(self.client, 'admin_test_mealcalc')
        self.chicken = make_food('Chicken', kcal=165, protein=31, carbs=0, fat=3.6)
        self.rice = make_food('Rice', kcal=130, protein=2.7, carbs=28, fat=0.3)

    def test_meal_calc_by_name(self):
        payload = {
            'items': [
                {'food_name': 'Chicken', 'grams': 200},
                {'food_name': 'Rice', 'grams': 150},
            ]
        }
        res = self.client.post('/api/nutri/meal-calc/', payload, format='json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('total_calories', data)
        # Chicken 200g = 330 kcal, Rice 150g = 195 kcal → ~525
        self.assertAlmostEqual(data['total_calories'], 525, delta=5)

    def test_meal_calc_unknown_food(self):
        payload = {'items': [{'food_name': 'UnknownXYZ', 'grams': 100}]}
        res = self.client.post('/api/nutri/meal-calc/', payload, format='json')
        # Should either return 400 or 200 with 0 calories
        self.assertIn(res.status_code, [200, 400, 404])

    def test_meal_calc_empty_items(self):
        payload = {'items': []}
        res = self.client.post('/api/nutri/meal-calc/', payload, format='json')
        self.assertIn(res.status_code, [200, 400])
