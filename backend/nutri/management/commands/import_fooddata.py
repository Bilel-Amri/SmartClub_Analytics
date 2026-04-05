"""
Management command: import_fooddata
=====================================
Imports USDA FoodData Central Foundation Foods into the nutri_food table.

Usage:
    python manage.py import_fooddata --path /path/to/FoodData_Central_csv/
    python manage.py import_fooddata   # uses settings.FOODDATA_PATH

Key nutrient IDs (from nutrient.csv):
    1008 → Energy (kcal)
    1003 → Protein (g)
    1005 → Carbohydrate (g)
    1004 → Total lipid/Fat (g)

Only Foundation Foods (data_type='foundation_food') are imported.
Duplicates are skipped (update_or_create on fdc_id).
"""

import os
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import pandas as pd
from nutri.models import Food


NUTRIENT_MAP = {
    1008: 'calories_100g',    # Energy kcal
    1003: 'protein_100g',     # Protein g
    1005: 'carbs_100g',       # Carbohydrate g
    1004: 'fat_100g',         # Total lipid g
}


class Command(BaseCommand):
    help = 'Import USDA FoodData Central Foundation Foods into the Food table.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--path', type=str, default=None,
            help='Path to the FoodData Central CSV directory (overrides settings.FOODDATA_PATH)',
        )
        parser.add_argument(
            '--limit', type=int, default=0,
            help='Maximum number of foods to import (0 = all)',
        )

    def handle(self, *args, **options):
        csv_dir = Path(options['path'] or getattr(settings, 'FOODDATA_PATH', ''))
        if not csv_dir.exists():
            raise CommandError(f"FoodData CSV directory not found: {csv_dir}")

        self.stdout.write(f"[NutriAI] Loading CSVs from {csv_dir} …")

        food_df = pd.read_csv(csv_dir / 'food.csv', dtype={'fdc_id': str})
        nutrient_df = pd.read_csv(csv_dir / 'nutrient.csv')
        fn_df = pd.read_csv(
            csv_dir / 'food_nutrient.csv',
            dtype={'fdc_id': str},
            low_memory=False
        )

        # Only foundation foods
        foundation = food_df[food_df['data_type'] == 'foundation_food'].copy()
        self.stdout.write(f"[NutriAI] Foundation foods found: {len(foundation)}")

        if options['limit']:
            foundation = foundation.head(options['limit'])

        # Filter nutrient rows to the 4 we care about
        fn_filtered = fn_df[fn_df['nutrient_id'].isin(NUTRIENT_MAP.keys())].copy()
        fn_filtered['nutrient_id'] = fn_filtered['nutrient_id'].astype(int)

        # Pivot: fdc_id → {nutrient_col: value}
        pivot = fn_filtered.pivot_table(
            index='fdc_id', columns='nutrient_id', values='amount', aggfunc='mean'
        )
        pivot.index = pivot.index.astype(str)
        pivot = pivot.rename(columns=NUTRIENT_MAP)

        created = updated = skipped = 0

        for _, row in foundation.iterrows():
            fdc_id = str(row['fdc_id'])
            name   = str(row['description'])[:150]

            if fdc_id not in pivot.index:
                skipped += 1
                continue

            nutrients = pivot.loc[fdc_id]
            kcal = nutrients.get('calories_100g', None)
            prot = nutrients.get('protein_100g', None)
            carb = nutrients.get('carbs_100g', None)
            fat  = nutrients.get('fat_100g', None)

            if any(v is None or (hasattr(v, '__class__') and str(v) == 'nan')
                   for v in [kcal, prot, carb, fat]):
                skipped += 1
                continue

            try:
                obj, was_created = Food.objects.update_or_create(
                    fdc_id=fdc_id,
                    defaults={
                        'name':          name,
                        'calories_100g': float(kcal),
                        'protein_100g':  float(prot),
                        'carbs_100g':    float(carb),
                        'fat_100g':      float(fat),
                        'source':        'usda',
                    }
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                # Duplicate name — append fdc_id to make unique
                try:
                    unique_name = f"{name} [{fdc_id}]"[:150]
                    obj, was_created = Food.objects.update_or_create(
                        fdc_id=fdc_id,
                        defaults={
                            'name':          unique_name,
                            'calories_100g': float(kcal),
                            'protein_100g':  float(prot),
                            'carbs_100g':    float(carb),
                            'fat_100g':      float(fat),
                            'source':        'usda',
                        }
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1
                except Exception as e2:
                    self.stderr.write(f"  SKIP {fdc_id} ({name}): {e2}")
                    skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n[NutriAI] Done — Created: {created}  Updated: {updated}  Skipped: {skipped}"
            )
        )
