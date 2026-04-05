import csv 
import json 
import logging 
import random 
from datetime import datetime, timedelta 
from pathlib import Path 
from django.core.management.base import BaseCommand 
from django.conf import settings 
from physio.models import PhysioHistoricalCase 
 
logger = logging.getLogger(__name__) 
 
class Command(BaseCommand): 
    help = 'Seeds historical physio cases from seed dataset.' 
 
    def __init__(self, *args, **kwargs): 
        super().__init__(*args, **kwargs) 
        self.seed_file = Path(settings.BASE_DIR).parent / 'seed' / 'injuries.csv' 
 
    def handle(self, *args, **options): 
        assert self.seed_file.exists(), f"Seed file not found: {self.seed_file}" 
        PhysioHistoricalCase.objects.all().delete() 
        self.stdout.write(self.style.WARNING("Deleted all existing historical cases.")) 
 
        created_count = 0 
        try: 
            with open(self.seed_file, encoding='utf-8') as f: 
                reader = list(csv.DictReader(f)) 
                for _ in range(10): 
                    for row in reader: 
                        days_absent = 1 
                        try: 
                            days_absent_str = row.get('days_absent', '7') 
                            days_absent = max(1, int(float(days_absent_str)) + random.randint(-2, 3)) 
                        except ValueError: 
                            pass 
 
                        player_name = row.get('player_full_name', row.get('player', 'Unknown Player')) 
                        injury_type = row.get('injury_type', row.get('injury', 'General Strain')) 
 
                        inj_lower = injury_type.lower() 
                        if 'hamstring' in inj_lower: 
                            primary_zone = 'hamstring' 
                        elif 'knee' in inj_lower: 
                            primary_zone = 'knee' 
                        elif 'ankle' in inj_lower: 
                            primary_zone = 'ankle' 
                        elif 'groin' in inj_lower: 
                            primary_zone = 'groin' 
                        else: 
                            primary_zone = 'multiple/other' 
 
                        PhysioHistoricalCase.objects.create( 
                            player_name=player_name, 
                            age=random.randint(18, 35), 
                            position=random.choice(['Forward', 'Midfielder', 'Defender', 'Goalkeeper']), 
                            injury_type=injury_type, 
                            primary_zone=primary_zone, 
                            context=random.choice(['training session', 'match', 'gym']), 
                            previous_injuries=random.randint(0, 3), 
                            previous_same_zone=random.randint(0, 1), 
                            recurrence_same_zone=str(row.get('recurrence', 'False')).lower() == 'true', 
                            training_load_band=random.choice(['low', 'medium', 'high']), 
                            days_since_last_intense=random.randint(1, 14), 
                            absence_days=days_absent, 
                            risk_score=random.randint(20, 85), 
                            outcome_label=row.get('severity', 'Moderate'), 
                            metadata={} 
                        ) 
                        created_count += 1 
            self.stdout.write(self.style.SUCCESS(f"Successfully seeded {created_count} historical cases.")) 
        except Exception as e: 
            self.stdout.write(self.style.ERROR(f"Error seeding historical cases: {str(e)}")) 
