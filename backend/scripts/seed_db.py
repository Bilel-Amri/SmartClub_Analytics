"""
seed_db.py – load CSV data into the database.
Run: python backend/scripts/seed_db.py
      OR from backend/: python manage.py shell < scripts/seed_db.py (not recommended)
      OR: python scripts/seed_db.py (from backend dir with DJANGO_SETTINGS_MODULE set)
"""
import os
import sys
import django
from pathlib import Path

# ── Setup Django ──────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartclub.settings')
django.setup()

# ruff: noqa: E402
import csv
from datetime import date
from decimal import Decimal

from scout.models import Player, Contract, PlayerMatchStats, PlayerEmbedding
from physio.models import Injury, TrainingLoad
from nutri.models import Food
from django.contrib.auth import get_user_model
User = get_user_model()

SEED_DIR = BACKEND_DIR.parent / 'seed'


def read_csv(name):
    path = SEED_DIR / name
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def seed_superuser():
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@smartclub.local', 'admin123')
        print('[✓] Superuser created: admin / admin123')
    else:
        print('[·] Superuser already exists')


def seed_players():
    rows = read_csv('players.csv')
    created = 0
    for row in rows:
        p, is_new = Player.objects.get_or_create(
            full_name=row['full_name'],
            defaults={
                'position': row['position'].strip(),
                'age': int(row['age']),
                'height_cm': float(row['height_cm']),
                'weight_kg': float(row['weight_kg']),
                'preferred_foot': row['preferred_foot'].strip(),
            }
        )
        if is_new:
            created += 1
    print(f'[✓] Players: {created} created ({Player.objects.count()} total)')


def seed_match_stats():
    """Synthetic match stats seeded per player for embedding generation."""
    import random
    random.seed(42)
    players = Player.objects.all()
    created = 0
    pos_profile = {
        'GK': dict(progressive_passes=10, carries=20, defensive_actions=60, duel_win_rate=0.65, crosses=2, xg_proxy=0.2, xa_proxy=0.1),
        'CB': dict(progressive_passes=25, carries=40, defensive_actions=55, duel_win_rate=0.60, crosses=3, xg_proxy=0.5, xa_proxy=0.3),
        'RB': dict(progressive_passes=45, carries=65, defensive_actions=35, duel_win_rate=0.55, crosses=30, xg_proxy=2, xa_proxy=4),
        'CM': dict(progressive_passes=60, carries=80, defensive_actions=30, duel_win_rate=0.52, crosses=10, xg_proxy=5, xa_proxy=6),
        'FW': dict(progressive_passes=30, carries=70, defensive_actions=15, duel_win_rate=0.50, crosses=8, xg_proxy=15, xa_proxy=8),
    }
    for p in players:
        profile = pos_profile.get(p.position, pos_profile['CM'])
        _, is_new = PlayerMatchStats.objects.get_or_create(
            player=p,
            season='2024-25',
            defaults={k: v + random.uniform(-v * 0.2, v * 0.2) for k, v in profile.items()}
        )
        if is_new:
            created += 1
    print(f'[✓] Match stats: {created} players seeded')


def seed_embeddings():
    """Embedding generation is intentionally disabled in this clean integration baseline."""
    print('[·] Embedding generation skipped (no bundled ML preprocessing).')


def seed_contracts():
    rows = read_csv('contracts.csv')
    created = 0
    for row in rows:
        try:
            player = Player.objects.get(full_name=row['player_full_name'])
        except Player.DoesNotExist:
            print(f'  [!] Player not found: {row["player_full_name"]}')
            continue
        _, is_new = Contract.objects.get_or_create(
            player=player,
            defaults={
                'salary_yearly': Decimal(row['salary_yearly_eur']),
                'transfer_fee': Decimal(row['transfer_fee_eur']),
                'start_date': date.fromisoformat(row['start_date']),
                'end_date': date.fromisoformat(row['end_date']),
            }
        )
        if is_new:
            created += 1
    print(f'[✓] Contracts: {created} created ({Contract.objects.count()} total)')


def seed_training_loads():
    rows = read_csv('training_loads.csv')
    created = 0
    for row in rows:
        try:
            player = Player.objects.get(full_name=row['player_full_name'])
        except Player.DoesNotExist:
            continue
        _, is_new = TrainingLoad.objects.get_or_create(
            player=player,
            date=date.fromisoformat(row['date']),
            defaults={
                'total_distance_km': float(row['total_distance_km']),
                'sprints': int(row['sprints']),
                'accelerations': int(row['accelerations']),
                'rpe': float(row['rpe']),
                'sleep_quality': int(row['sleep_quality']),
                'minutes_played': int(row.get('minutes_played', 0)),
            }
        )
        if is_new:
            created += 1
    print(f'[✓] Training loads: {created} created ({TrainingLoad.objects.count()} total)')


def seed_injuries():
    rows = read_csv('injuries.csv')
    created = 0
    for row in rows:
        try:
            player = Player.objects.get(full_name=row['player_full_name'])
        except Player.DoesNotExist:
            continue
        inj, is_new = Injury.objects.get_or_create(
            player=player,
            injury_type=row['injury_type'],
            date=date.fromisoformat(row['date']),
            defaults={
                'severity': row['severity'],
                'days_absent': int(row['days_absent']),
                'matches_missed': int(row['matches_missed']),
                'recurrence_flag': row.get('recurrence', 'false').strip().lower() == 'true',
            }
        )
        if is_new:
            created += 1
    print(f'[✓] Injuries: {created} created ({Injury.objects.count()} total)')


def seed_foods():
    rows = read_csv('foods.csv')
    created = 0
    for row in rows:
        _, is_new = Food.objects.get_or_create(
            name=row['name'],
            defaults={
                'calories_100g': float(row['calories_100g']),
                'protein_100g': float(row['protein_100g']),
                'carbs_100g': float(row['carbs_100g']),
                'fat_100g': float(row['fat_100g']),
                'source': row.get('source', 'manual'),
            }
        )
        if is_new:
            created += 1
    print(f'[✓] Foods: {created} created ({Food.objects.count()} total)')


if __name__ == '__main__':
    print('=== SmartClub Analytics – Seeding DB ===')
    seed_superuser()
    seed_players()
    seed_contracts()
    seed_training_loads()
    seed_injuries()
    seed_foods()
    seed_match_stats()
    seed_embeddings()
    print('=== Done! ===')
