import os  
import django  
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smartclub.settings")  
django.setup()  
from physio.models import GlobalPlayer  
profiles = [{"prefix":"Veteran (CB)","team":"TeamA"}, {"prefix":"Prospect (LW)","team":"TeamA"}, {"prefix":"Box-to-Box (CM)","team":"TeamA"}, {"prefix":"Target (ST)","team":"TeamB"}, {"prefix":"Playmaker (CAM)","team":"TeamB"}]  
players = list(GlobalPlayer.objects.all())  
for i, p in enumerate(players):  
    prof = profiles[i %% len(profiles)]  
    p.external_id = f"{prof['prefix']} #{i+1}"  
    p.team = prof['team']  
    p.position = prof['prefix'].split('(')[-1].replace(')','')  
    p.save()  
