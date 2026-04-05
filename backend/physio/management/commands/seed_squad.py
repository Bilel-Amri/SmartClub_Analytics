from django.core.management.base import BaseCommand
from django.utils import timezone
import random
from datetime import timedelta
from scout.models import Player
from physio.models import Injury, TrainingLoad

class Command(BaseCommand):
    help = 'Seeds 20 realistic squad players with injuries and training data.'

    def handle(self, *args, **kwargs):
        demo_names = ['Explosive (FW)', 'Playmaker (CM)', 'Veteran (CB)']
        Player.objects.exclude(full_name__in=demo_names).delete()

        self.stdout.write("Generating 20 squad players...")
        first_names = ['Carlos', 'Javier', 'Liam', 'Noah', 'Oliver', 'Elijah', 'Lucas', 'Leo', 'Ethan', 'Marcus', 'David', 'John', 'Alex']
        last_names = ['Silva', 'Garcia', 'Martinez', 'Lopez', 'Hernandez', 'Perez', 'Sanchez', 'Torres', 'Rivera', 'Gomez', 'Diaz']
        positions = ['GK', 'CB', 'CB', 'LB', 'RB', 'CDM', 'CM', 'CM', 'CAM', 'LW', 'RW', 'FW', 'FW', 'FW', 'LB', 'RB', 'CB']
        zonas = ['Hamstring', 'Quadriceps', 'Calf', 'Groin', 'Ankle', 'Knee', 'Adductor']
        
        today = timezone.now().date()
        players_created = 0
        for i in range(20):
            fname = random.choice(first_names)
            lname = random.choice(last_names)
            full_name = f"{fname} {lname} {i+1}"
            pos = random.choice(positions)
            age = random.randint(18, 35)
            
            p = Player.objects.create(
                full_name=full_name,
                position=pos,
                age=age,
                height_cm=random.randint(170, 195),
                weight_kg=random.randint(65, 90)
            )
            
            num_injuries = random.randint(0, 3)
            for _ in range(num_injuries):
                days_ago = random.randint(10, 700)
                inj_date = today - timedelta(days=days_ago)
                Injury.objects.create(
                    player=p,
                    injury_type=random.choice(zonas),
                    date=inj_date,
                    severity=random.choice(['mild', 'moderate', 'severe']),
                    days_absent=random.randint(3, 40)
                )
                
            for d in range(7):
                tl_date = today - timedelta(days=d)
                TrainingLoad.objects.create(
                    player=p,
                    date=tl_date,
                    total_distance_km=random.uniform(3.0, 12.0),
                    sprints=random.randint(5, 30),
                    accelerations=random.randint(10, 50),
                    rpe=random.uniform(4.0, 9.0),
                    minutes_played=120
                )
            
            players_created += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully created {players_created} players with injury history and training load."))
