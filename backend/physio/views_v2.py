from __future__ import annotations

from datetime import date, timedelta
from statistics import mean

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status, views
from rest_framework.response import Response

from scout.models import Player
from physio.prediction_service import prediction_service

from .groq_layer import generate_explanation
from .models import (
    Injury,
    PhysioAIExplanation,
    PhysioAbsencePredictionRun,
    PhysioHistoricalCase,
    PhysioRiskSimulationRun,
    PhysioSimilarityMatch,
    PhysioSquadSnapshot,
    TrainingLoad,
)
from .permissions import IsCoachOrAbove
from .similarity_service import similar_for_absence, similar_for_risk
from .vulnerability_formula import compute_vulnerability_score


def _latest_zone(player: Player) -> str:
    latest = player.injuries.order_by("-date").first()
    if not latest:
        return "other"
    txt = (latest.injury_type or "other").lower()
    for zone in ["hamstring", "groin", "knee", "ankle", "calf", "back", "thigh"]:
        if zone in txt:
            return zone
    return "other"


def _load_band(player: Player) -> str:
    recent = list(player.training_loads.order_by("-date")[:5])
    if not recent:
        return "medium"
    dists = [float(r.total_distance_km or 0.0) for r in recent]
    avg = mean(dists) if dists else 0.0
    if avg >= 10.0:
        return "high"
    if avg <= 5.0:
        return "low"
    return "medium"


def _days_since_last_intense(player: Player) -> int:
    intense = player.training_loads.filter(rpe__gte=8).order_by("-date").first()
    if not intense:
        return 5
    return max((timezone.now().date() - intense.date).days, 0)


def _driver_texts(result: dict) -> list[str]:
    out = []
    for d in result.get("top_drivers", []):
        if d["label"] == "Previous injuries":
            out.append("Accumulated prior injuries increase recurrence profile")
        elif d["label"] == "Primary injury zone":
            out.append("Primary zone history indicates tissue stress concentration")
        elif d["label"] == "Training load":
            out.append("Current load context raises tolerance risk")
        elif d["label"] == "Recovery window":
            out.append("Short recovery window reduces resilience")
        else:
            out.append(f"{d['label']} contributes to current risk")
    return out[:4]


class SquadDailyRiskView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def get(self, request):
        today = timezone.now().date()
        rows = []
        seen_player_names = set()

        demo_names = ["Explosive (FW)", "Playmaker (CM)", "Veteran (CB)"]
        active_cutoff = today - timedelta(days=365) # Show data up to 1 year back for seeded databases
        real_players = (
            Player.objects.exclude(full_name__in=demo_names)
            .filter(Q(training_loads__date__gte=active_cutoff) | Q(injuries__date__gte=active_cutoff))
            .distinct()
            .order_by("full_name")
        )
        
        if not real_players.exists():
            return Response({"empty": True, "message": "No squad data available yet. Add players or sync data."})

        for p in real_players:
            name_key = (p.full_name or "").strip().lower()
            if name_key and name_key in seen_player_names:
                continue
            if name_key:
                seen_player_names.add(name_key)

            previous_injuries = p.injuries.count()
            last_two = p.injuries.filter(date__gte=today.replace(year=today.year - 2)).count()
            zone = _latest_zone(p)
            load_band = _load_band(p)
            days_since = _days_since_last_intense(p)
            recurrence = p.injuries.filter(injury_type__icontains=zone).count() >= 2

            payload = {
                "age": int(p.age or 25),
                "position": str(p.position or "midfielder"),
                "previous_injuries": previous_injuries,
                "injuries_last_2_seasons": last_two,
                "primary_zone": zone,
                "training_load_band": load_band,
                "days_since_last_intense": days_since,
                "recurrence_same_zone": recurrence,
                "player_id": p.id,
            }

            latest_load = p.training_loads.order_by("-date").first()
            if latest_load:
                payload["readiness_value"] = latest_load.readiness or 0.0
                payload["soreness_value"] = latest_load.soreness or 0.0
                payload["sleep_quality_value"] = latest_load.sleep_quality or 0.0
                # Proxy fatigue and stress using RPE
                payload["fatigue_value"] = latest_load.rpe or 0.0
                payload["stress_value"] = latest_load.rpe or 0.0
                
                # Approximate load metrics
                payload["daily_load_value"] = (latest_load.rpe or 0) * (latest_load.minutes_played or 0)
                
                recent_loads = p.training_loads.order_by("-date")[:7]
                wk_load = sum((l.rpe or 0) * (l.minutes_played or 0) for l in recent_loads)
                payload["weekly_load_value"] = wk_load
            
            try:
                scored = prediction_service.risk.predict(payload)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"predict_risk() failed in SquadDailyRiskView for player {p.id}, falling back.")
                scored = {"success": False}
            
            if not scored.get("success", True):
                # Fallback to compute_vulnerability_score if model prediction simply wasn't successful
                scored = compute_vulnerability_score(**payload)
            else:
                scored.setdefault("breakdown", {})
                # Make sure the payload matches expected keys for downstream rules
                scored["risk_score"] = scored.get("risk_index", scored.get("risk_score", 0))

            drivers = _driver_texts(scored)
            decision = {
                "load": "reduce max-speed exposure" if scored["risk_band"] == "high" else "normal session control",
                "session": "technical phases only" if scored["risk_band"] != "low" else "normal",
                "monitor": "physio check before start" if scored["risk_band"] != "low" else "routine monitoring",
                "escalation": "stop session if discomfort reported" if scored["risk_band"] == "high" else "refer if symptoms persist",
            }

            snapshot, _ = PhysioSquadSnapshot.objects.update_or_create(
                player=p,
                snapshot_date=today,
                defaults={
                    "risk_score": scored["risk_score"],
                    "risk_band": scored["risk_band"],
                    "previous_injuries": previous_injuries,
                    "primary_zone": zone,
                    "training_load_band": load_band,
                    "days_since_last_intense": days_since,
                    "top_drivers": drivers,
                    "actions": decision,
                },
            )

            injury_history = [
                {
                    "injury_type": i.injury_type,
                    "days_absent": i.days_absent,
                    "date": i.date.isoformat(),
                }
                for i in p.injuries.order_by("-date")[:4]
            ]

            rows.append(
                {
                    "snapshot_id": snapshot.id,
                    "player_id": p.id,
                    "player_name": p.full_name,
                    "position": p.position,
                    "age": p.age,
                    "risk_score": scored["risk_score"],
                    "risk_band": scored["risk_band"],
                    "risk_drivers": drivers,
                    "decision": decision,
                    "injury_history": injury_history,
                }
            )

        protect = [r for r in rows if r["risk_band"] == "high"]
        monitor = [r for r in rows if r["risk_band"] == "medium"]
        ready = [r for r in rows if r["risk_band"] == "low"]

        protect_unique = {str(r.get("player_name", "")).strip().lower() for r in protect if r.get("player_name")}
        monitor_unique = {str(r.get("player_name", "")).strip().lower() for r in monitor if r.get("player_name")}
        ready_unique = {str(r.get("player_name", "")).strip().lower() for r in ready if r.get("player_name")}
        injured_cutoff = today - timedelta(days=30)
        injured_unique = set(
            Injury.objects.filter(date__gte=injured_cutoff, days_absent__gt=0).values_list("player_id", flat=True)
        )

        return Response(
            {
                "date": today.isoformat(),
                "summary": {
                    "protect_today": len(protect_unique),
                    "monitor_closely": len(monitor_unique),
                    "ready_to_train": len(ready_unique),
                    "injured": len(injured_unique),
                },
                "groups": {
                    "protect_today": protect,
                    "monitor_closely": monitor,
                    "ready_to_train": ready,
                },
            }
        )


class PlayerRiskSimulatorView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def post(self, request):
        from physio.prediction_service import prediction_service
        
        payload = request.data
        
        try:
            result = prediction_service.risk.predict(payload)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"predict_risk() failed: {e}")
            result = {"success": False}
        
        if not result.get("success"):
            # Provide fallback without 500 error when ML isn't installed
            fallback = compute_vulnerability_score(**payload)
            r_band = fallback.get("risk_band", "medium")
            
            # Extract string labels from top_drivers dicts for the frontend
            driver_labels = [d.get("label", str(d)) if isinstance(d, dict) else str(d) for d in fallback.get("top_drivers", [])]

            result = {
                "success": True,
                "risk_index": fallback.get("risk_score", 50),
                "risk_band": r_band,
                "raw_probability": fallback.get("risk_score", 50) / 100.0,
                "key_risk_drivers": driver_labels,
                "training_decision": {
                    "load": "reduce load" if r_band == "high" else "normal",
                    "session": "modify phase" if r_band == "high" else "full",
                    "escalation": "refer to physio" if r_band != "low" else "none"
                },
                "model_status": "fallback_rules",
                "input_quality_status": "ok",
                "missing_fields": [],
                "applied_defaults": {}
            }

        sim_matches = similar_for_risk(payload, k=3)
        sim_profiles = [
            {
                "summary": m.summary,
                "match_pct": float(m.match_pct),
                "player_name": m.payload.get("player_name"),
                "position": m.payload.get("position"),
                "age": m.payload.get("age"),
            }
            for m in sim_matches
        ]

        # Fallback to live Player table when no historical rows are available.
        if not sim_profiles:
            target_age = float(payload.get("age", 25) or 25)
            target_pos = str(payload.get("position", "")).strip().lower()
            target_name = str(payload.get("player_name", "")).strip().lower()
            candidates = []

            qs = Player.objects.exclude(full_name__isnull=True).exclude(full_name__exact="").order_by("full_name")
            for p in qs[:300]:
                p_name = (p.full_name or "").strip()
                if target_name and p_name.lower() == target_name:
                    continue
                p_age = float(p.age or 25)
                p_pos = str(p.position or "").strip().lower()
                distance = abs(p_age - target_age) + (0.0 if p_pos == target_pos else 5.0)
                match_pct = round((1.0 / (1.0 + max(distance, 0.0))) * 100.0, 1)
                candidates.append(
                    {
                        "summary": f"{p_name} ({p.position or 'Player'} · Age {int(p_age)})",
                        "match_pct": match_pct,
                        "player_name": p_name,
                        "position": p.position,
                        "age": int(p_age),
                        "_distance": distance,
                    }
                )

            candidates.sort(key=lambda x: x["_distance"])
            used_names = set()
            for c in candidates:
                n_key = c["player_name"].strip().lower()
                if n_key in used_names:
                    continue
                used_names.add(n_key)
                c.pop("_distance", None)
                sim_profiles.append(c)
                if len(sim_profiles) >= 3:
                    break
            
        # Match legacy frontend shape alongside new data 
        response_data = {
            "risk_score": result["risk_index"],
            "risk_band": result["risk_band"],
            "raw_probability": result["raw_probability"],
            "risk_drivers": result["key_risk_drivers"],
            "decision": {
                "training_decision": [
                    f"Load: {result['training_decision']['load']}",
                    f"Session: {result['training_decision']['session']}",
                ],
                "monitoring_plan": [
                    "Physio assessment before session",
                    "Daily RPE monitoring — flag if > 7/10",
                ],
                "escalation_rule": [
                    result['training_decision']['escalation'],
                    "Refer to physio if pain persists post-session"
                ],
            },
            "similar_profiles": sim_profiles,
            "model_status": result["model_status"],
            "input_quality_status": result["input_quality_status"],
            "missing_fields": result["missing_fields"],
            "applied_defaults": result.get("applied_defaults", {}),
            "metadata_labels": result.get("metadata_labels", {}),
            "run_id": 1
        }
        
        return Response(response_data)

class AbsencePredictionView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def post(self, request):
        from physio.prediction_service import prediction_service

        payload = request.data

        # Rule 1: Fallback when ML fails to avoid 400 errors if pandas isn't installed
        try:
            result = prediction_service.absence.predict(payload)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Absence model prediction failed: {e}", exc_info=True)
            result = {"success": False}

        if not result.get("success"):
            # Provide a smart fallback payload so the UI doesn't crash
            # Basic rule: default to 14 days
            base_days = 14
            if payload.get("primary_zone") in ["knee", "hamstring"]:
                base_days = 28
            elif payload.get("primary_zone") in ["ankle", "groin"]:
                base_days = 21

            result = {
                "success": True,
                "raw_predicted_days": base_days * 0.95,
                "predicted_days": base_days,
                "severity_bucket": "moderate" if base_days <= 21 else "severe",
                "severity_label": "Moderate" if base_days <= 21 else "Severe",
                "predicted_range": f"{max(7, base_days-3)}-{base_days+5} days",
                "confidence": 0.65,
                "explanation": ["Based on historical fallback rules.", f"Zone severity accounts for {base_days}d baseline."],
                "recommended_actions": {
                    "participation": "Out of full training",
                    "medical": "Physio review",
                    "coach_notification": "Inform coach",
                    "escalation": "Stop if pain"
                },
                "model_status": "fallback_rules",
                "input_quality_status": "ok",
                "missing_fields": [],
            }

        # Rule 3: Return exact similar profiles ensuring deduplication 
        payload["absence_anchor_days"] = result["predicted_days"]
        sim_matches = similar_for_absence(payload, k=3)
        sim_profiles = [
            {
                "player_name": m.payload.get("player_name"),
                "absence_days": m.payload.get("absence_days"),
                "match_pct": float(m.match_pct)
            }
            for m in sim_matches
        ]

        response_data = {
            "raw_predicted_days": result.get("raw_predicted_days"),
            "predicted_days": result["predicted_days"],
            "severity_bucket": result["severity_bucket"],
            "formatted_bucket_display": f"{result['severity_label'].capitalize()} absence · {result['predicted_range']}",
            "confidence": result["confidence"],
            "explanation": result["explanation"],
            "recommended_actions": result["recommended_actions"],
            "model_status": result["model_status"],
            "input_quality_status": result["input_quality_status"],
            "missing_fields": result["missing_fields"],
            "applied_defaults": result.get("applied_defaults", {}),
            "similar_profiles": result.get("similar_profiles", []),
            "metadata_labels": result.get("metadata_labels", {}),
            "run_id": 1
        }

        # Keep some old keys matching expected frontend parsing if needed
        response_data["severity_score"] = 100 if result["severity_bucket"] == "43_plus" else 50
        response_data["severity_class"] = result["severity_label"]
        response_data["immediate_actions"] = {
            "participation": result["recommended_actions"].get("participation", "Out of full training"),
            "medical": result["recommended_actions"].get("medical", "Physio review"),
            "coach_notification": result["recommended_actions"].get("coach_notification", "Inform coach"),
            "escalation": result["recommended_actions"].get("escalation", "Stop if pain")
        }
        response_data["historical_case_matching"] = {
            "count": len(sim_profiles),
            "average_days": str(int(sum(c["absence_days"] for c in sim_profiles) / len(sim_profiles))) if sim_profiles else "-",
            "median_days": str(sorted([c["absence_days"] for c in sim_profiles])[len(sim_profiles)//2]) if sim_profiles else "-",
            "shortest_days": str(min(c["absence_days"] for c in sim_profiles)) if sim_profiles else "-",
            "longest_days": str(max(c["absence_days"] for c in sim_profiles)) if sim_profiles else "-",
            "cases": sim_profiles
        }
        
        response_data["similar_profiles"] = sim_profiles

        return Response(response_data)


class PhysioMLHealthView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def get(self, request):
        from physio.prediction_service import prediction_service

        schema = getattr(prediction_service, "absence_schema", {}) or {}
        manifest = getattr(prediction_service, "manifest", {}) or {}
        modules = manifest.get("modules", {}) if isinstance(manifest, dict) else {}
        severity = modules.get("absence_days", {}) if isinstance(modules, dict) else {}

        return Response(
            {
                "prediction_service_ready": bool(getattr(prediction_service, "ready_state", False)),
                "prediction_service_error": getattr(prediction_service, "last_error", None),
                "model_name": severity.get("algorithm") or manifest.get("model_name") or "RandomForest",
                "model_version": manifest.get("version") or "v1",
                "auc": schema.get("roc_auc", 0.656),
                "cv_auc": schema.get("cv_auc_mean"),
                "artifacts": {
                    "all_features": getattr(prediction_service, "absence_schema", {}).get("input_features_ordered", []),
                    "position_values": [],
                    "injury_values": [],
                },
            }
        )


class ExplainWithAIView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def post(self, request):
        # User-triggered only endpoint.
        function_type = str(request.data.get("function_type", "player_risk_simulator"))
        payload = request.data.get("payload", {})

        explained = generate_explanation(function_type, payload)

        simulation_run = None
        absence_run = None
        run_id = request.data.get("run_id")
        if run_id:
            if function_type == "player_risk_simulator":
                simulation_run = PhysioRiskSimulationRun.objects.filter(pk=run_id).first()
            elif function_type == "absence_prediction":
                absence_run = PhysioAbsencePredictionRun.objects.filter(pk=run_id).first()

        log = PhysioAIExplanation.objects.create(
            function_type=function_type,
            requester=request.user if request.user.is_authenticated else None,
            simulation_run=simulation_run,
            absence_run=absence_run,
            request_payload=payload if isinstance(payload, dict) else {"raw": payload},
            response_text=explained["text"],
            provider=explained["provider"],
            fallback_used=explained["fallback_used"],
        )

        return Response(
            {
                "id": log.id,
                "text": log.response_text,
                "provider": log.provider,
                "fallback_used": log.fallback_used,
                "created_at": log.created_at,
            },
            status=status.HTTP_200_OK,
        )


class SimilaritySeedView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def post(self, request):
        if PhysioHistoricalCase.objects.exists():
            return Response({"detail": "Historical cases already seeded."})

        sample = [
            ("L.Mora", 27, "Striker", "Hamstring recurrence", "hamstring", "training", 3, 2, True, "high", 2, 21, 75),
            ("R.Vega", 30, "Winger", "Hamstring recurrence", "hamstring", "training", 4, 2, True, "high", 2, 28, 84),
            ("K.Diaz", 29, "Forward", "Hamstring recurrence", "hamstring", "training", 4, 2, True, "medium", 3, 24, 79),
            ("C.Park", 28, "Central Midfielder", "Groin recurring", "groin", "training", 3, 1, True, "high", 2, 18, 68),
            ("H.Tran", 27, "CM", "Thigh/groin zone", "thigh", "training", 2, 1, False, "medium", 3, 14, 55),
            ("K.Mason", 30, "Midfielder", "Back and groin", "back", "training", 4, 1, False, "high", 2, 36, 72),
            ("A.Lopes", 29, "Striker", "Hamstring", "hamstring", "training", 4, 2, True, "high", 2, 34, 75),
            ("O.Backer", 31, "Centre-back", "Hamstring", "hamstring", "match", 5, 2, True, "high", 1, 28, 84),
            ("J.Dubois", 22, "Right wing", "Ankle", "ankle", "training", 2, 1, False, "medium", 2, 9, 47),
        ]

        created = 0
        for s in sample:
            PhysioHistoricalCase.objects.create(
                player_name=s[0],
                age=s[1],
                position=s[2],
                injury_type=s[3],
                primary_zone=s[4],
                context=s[5],
                previous_injuries=s[6],
                previous_same_zone=s[7],
                recurrence_same_zone=s[8],
                training_load_band=s[9],
                days_since_last_intense=s[10],
                absence_days=s[11],
                risk_score=s[12],
                outcome_label="high" if s[12] >= 60 else "medium",
            )
            created += 1

        return Response({"created": created})

class PhysioPlayersProfileView(views.APIView):
    permission_classes = [IsCoachOrAbove]
    def get(self, request):
        demo_names = ['Explosive (FW)', 'Playmaker (CM)', 'Veteran (CB)']
        real_players = Player.objects.exclude(full_name__in=demo_names).order_by('full_name')
        out = []
        for p in real_players:
            out.append({
                'id': p.id,
                'player_name': p.full_name,
                'age': int(p.age or 25),
                'position': str(p.position or 'Midfielder'),
                'previous_injuries': p.injuries.count(),
                'injuries_last_2_seasons': p.injuries.count(),
                'primary_zone': _latest_zone(p),
                'training_load_band': _load_band(p),
                'days_since_last_intense': _days_since_last_intense(p),
                'recurrence_same_zone': False
            })
        return Response(out)
