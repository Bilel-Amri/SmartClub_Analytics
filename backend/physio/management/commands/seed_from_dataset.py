from django.core.management.base import BaseCommand
import csv
import os
from physio.models import PhysioHistoricalCase
from django.conf import settings

class Command(BaseCommand):
    help = "Seeds historical cases from preview dataset"

    def handle(self, *args, **options):
        csv_path = os.path.join(settings.BASE_DIR.parent, "seed", "absence_validation_preview.csv")
        self.stdout.write(f"Reading from {csv_path}")
        
        # Delete existing
        count_before = PhysioHistoricalCase.objects.count()
        PhysioHistoricalCase.objects.all().delete()
        self.stdout.write(f"Deleted {count_before} existing cases.")

        added = 0
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("player_name", "").strip()
                if not name or name.lower() == "nan":
                    continue
                
                days_capped_str = row.get("days_capped", "").strip()
                if not days_capped_str or days_capped_str.lower() == "nan":
                    continue
                
                try:
                    days_capped = float(days_capped_str)
                    if days_capped == 0:
                        continue
                except ValueError:
                    continue
                
                PhysioHistoricalCase.objects.create(
                    player_name=name,
                    injury_type=row.get("injury", "Unknown"),
                    absence_days=int(days_capped),
                    age=25,
                    position="Unknown",
                    primary_zone="Unknown",
                    metadata={
                        "club": row.get("club", ""),
                        "league": row.get("league", ""),
                        "season": row.get("season", "")
                    }
                )
                added += 1
        
        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {added} cases."))
        
        final_count = PhysioHistoricalCase.objects.count()
        self.stdout.write(f"Final PhysioHistoricalCase count: {final_count}")
