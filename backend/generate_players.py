import random  
from datetime import date, timedelta  
import django, os, sys  
sys.path.append('.')  
os.environ['DJANGO_SETTINGS_MODULE']='smartclub.settings'  
django.setup()  
from physio.models import Player, TrainingLoad, Injury  
Player.objects.all().delete()  
p1 = Player.objects.create(full_name='Veteran (CB)', position='CB', height_cm=190, weight_kg=85)  
p2 = Player.objects.create(full_name='Explosive (FW)', position='FW', height_cm=175, weight_kg=72)  
p3 = Player.objects.create(full_name='Playmaker (CM)', position='CM', height_cm=181, weight_kg=76)  
start_date = date.today() - timedelta(days=60)  
loads = []  
for i in range(60):  
    d = start_date + timedelta(days=i)  
    loads.append(TrainingLoad(player=p1, date=d, rpe=random.uniform(4, 7), total_distance_km=random.uniform(5, 8), sleep_quality=random.uniform(5, 8)))  
    loads.append(TrainingLoad(player=p2, date=d, rpe=random.uniform(7, 9), total_distance_km=random.uniform(9, 13), sleep_quality=random.uniform(7, 9)))  
    loads.append(TrainingLoad(player=p3, date=d, rpe=random.uniform(5, 8), total_distance_km=random.uniform(8, 12), sleep_quality=random.uniform(6, 8)))  
TrainingLoad.objects.bulk_create(loads)  
