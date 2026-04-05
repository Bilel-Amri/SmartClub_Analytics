from __future__ import annotations

from datetime import date
from statistics import mean

from django.db.models import Count
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

        demo_names = ["Explosive (FW)", "Playmaker (CM)", "Veteran (CB)"]
        real_players = Player.objects.exclude(full_name__in=demo_names).order_by("full_name")
        
        if not real_players.exists():
            return Response({"empty": True, "message": "No squad data available yet. Add players or sync data."})

        for p in real_players:
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
            
            if getattr(prediction_service, "ready_state", False) and getattr(prediction_service, "risk_model", None):
                scored = prediction_service.predict_risk(payload)
                scored.setdefault("breakdown", {})
            else:
                scored = compute_vulnerability_score(**payload)

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

        return Response(
            {
                "date": today.isoformat(),
                "summary": {
                    "protect_today": len(protect),
                    "monitor_closely": len(monitor),
                    "ready_to_train": len(ready),
                    "injured": Injury.objects.filter(days_absent__gt=0).values("player_id").distinct().count(),
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
        payload = {
            "age": int(request.data.get("age", 25)),
            "position": str(request.data.get("position", "Midfielder")),
            "previous_injuries": int(request.data.get("previous_injuries", 0)),
            "injuries_last_2_seasons": int(request.data.get("injuries_last_2_seasons", 0)),
            "primary_zone": str(request.data.get("primary_zone", "hamstring")),
            "training_load_band": str(request.data.get("training_load_band", "medium")).lower(),
            "days_since_last_intense": int(request.data.get("days_since_last_intense", 2)),
            "recurrence_same_zone": bool(request.data.get("recurrence_same_zone", False)),
            # NEW ML FIELDS:
            "sleep_duration_value": float(request.data.get("sleep_duration_value", 8)),
            "fatigue_value": float(request.data.get("fatigue_value", 2)),
            "stress_value": float(request.data.get("stress_value", 2)),
            "weekly_load_value": float(request.data.get("weekly_load_value", 1500)),
        }

        base_scores = compute_vulnerability_score(**payload)

        if getattr(prediction_service, "ready_state", False) and getattr(prediction_service, "risk_model", None):
            ml_result = prediction_service.predict_risk(payload)
            
            # Blend the standard physiological vulnerability formula with the CatBoost daily model output
            ml_weight = 0.4
            blended_score = max(0, min(100, int((base_scores["risk_score"] * (1 - ml_weight)) + (ml_result["risk_score"] * ml_weight))))
            
            if blended_score < 35:
                band = "low"
            elif blended_score < 60:
                band = "medium"
            else:
                band = "high"

            scored = {
                "risk_score": blended_score,
                "risk_band": band,
                "breakdown": base_scores["breakdown"],
                "top_drivers": base_scores["top_drivers"],
                "recommendation": ml_result.get("recommendation", "Cleared for Training"),
                "model_type": ml_result.get("model_type", "Formula + ML")
            }
        else:
            scored = base_scores

        decision = {
            "training_decision": [
                "Load: reduce max-speed and acceleration" if scored["risk_band"] == "high" else "Load: keep controlled progression",
                "Session: technical phases only" if scored["risk_band"] != "low" else "Session: normal plan",
            ],
            "monitoring_plan": [
                "Physio assessment before session",
                "Daily RPE monitoring — flag if > 7/10",
            ],
            "escalation_rule": [
                "Stop if hamstring discomfort reported",
                "Refer to physio if pain persists post-session",
            ],
        }

        run = PhysioRiskSimulationRun.objects.create(
            requester=request.user if request.user.is_authenticated else None,
            age=payload["age"],
            position=payload["position"],
            previous_injuries=payload["previous_injuries"],
            injuries_last_2_seasons=payload["injuries_last_2_seasons"],
            primary_zone=payload["primary_zone"],
            training_load_band=payload["training_load_band"],
            days_since_last_intense=payload["days_since_last_intense"],
            risk_score=scored["risk_score"],
            risk_band=scored["risk_band"],
            risk_drivers=_driver_texts(scored),
            recommendation_blocks=decision,
        )

        matches = similar_for_risk(payload, k=3)
        for m in matches:
            case = PhysioHistoricalCase.objects.filter(pk=m.case_id).first()
            if not case:
                continue
            PhysioSimilarityMatch.objects.create(
                function_type="player_risk_simulator",
                simulation_run=run,
                case=case,
                rank=m.rank,
                distance=m.distance,
                match_pct=m.match_pct,
                summary=m.summary,
            )

        run.similar_profiles_count = len(matches)
        run.save(update_fields=["similar_profiles_count"])

        return Response(
            {
                "run_id": run.id,
                "risk_score": run.risk_score,
                "risk_band": run.risk_band,
                "risk_drivers": run.risk_drivers,
                "decision": run.recommendation_blocks,
                "similar_profiles": [
                    {
                        "rank": m.rank,
                        "match_pct": m.match_pct,
                        "summary": m.summary,
                        "case": m.payload,
                    }
                    for m in matches
                ],
            }
        )


class AbsencePredictionView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def post(self, request):
        from physio.prediction_service import prediction_service

        age = int(request.data.get("age", 25))
        position = str(request.data.get("position", "Midfielder"))
        injury_type = str(request.data.get("injury_type", "Hamstring"))
        context = str(request.data.get("context", "training session"))
        previous_same_zone = int(request.data.get("previous_same_zone", 0))
        recurrence = bool(request.data.get("recurrence_same_zone", previous_same_zone > 0))
        player_name = str(request.data.get("player_name", "Unknown player"))
        load_band = str(request.data.get("training_load_band", "medium")).lower()

        severity_score = 0.62
        severity_class = "long"
        expected_label = "3-6 weeks"
        predicted_days = None
        severity_bucket = None
        model_type = "fallback"

        if getattr(prediction_service, "ready_state", False):
            if getattr(prediction_service, "absence_model", None):
                # Map to new regression model payload
                import datetime
                today = datetime.date.today()
                payload = {
                    "player_age": age,
                    "injury_group": injury_type,
                    "player_position": position,
                    "player_name": player_name,
                    "injury_year": today.year,
                    "injury_month": today.month,
                    "injury_day": today.day,
                    "injury_dow": today.weekday(),
                    "injury_weekofyear": today.isocalendar()[1]
                }
                pred = prediction_service.predict_absence(payload)
                predicted_days = pred.get("predicted_days")
                severity_bucket = pred.get("severity_bucket")
                expected_label = pred.get("bucket_label", expected_label)
                model_type = pred.get("model_type", "CatBoostRegressor")
                
                # Derive old fields for backwards compatibility with run object
                severity_score = 1.0 if severity_bucket in ["22_42", "43_plus"] else 0.4
                severity_class = "long" if predicted_days >= 22 else "short"
                
            elif getattr(prediction_service, "severity_model", None):
                pred = prediction_service.severity_predict(
                    age=age,
                    previous_injury_count=previous_same_zone,
                    position=position,
                    injury_type=injury_type,
                )
                severity_score = float(pred.get("severity_score", severity_score))
                severity_class = pred.get("severity", severity_class)
                expected_label = pred.get("expected_return", expected_label)
                model_type = "legacy_classification"

        if predicted_days is not None:
            days_min = predicted_days - 2
            days_max = predicted_days + 4
            conf = "high"
        elif severity_score >= 0.75:
            days_min, days_max, conf = 36, 48, "high"
        elif severity_score >= 0.55:
            days_min, days_max, conf = 21, 35, "medium"
        else:
            days_min, days_max, conf = 7, 20, "medium"

        # Make actions dynamically respond to severity bucket
        if severity_bucket == "0_7":
            actions = {
                "participation": "Modify training intensity. Monitor discomfort.",
                "medical": "Standard physio review tomorrow prior to warm-up.",
                "coach_notification": "Inform coach of minor knock — available for next match if clears test.",
                "escalation": "Stop training only if acute pain returns.",
            }
        elif severity_bucket == "8_21":
            actions = {
                "participation": "Out of full training. Individual rehab only.",
                "medical": "Clinical review needed. Ultrasound if symptoms persist > 48h.",
                "coach_notification": "Will miss upcoming fixture. Individual return-to-play plan starting.",
                "escalation": "Full rest from sprinting mechanisms.",
            }
        elif severity_bucket == "22_42":
            actions = {
                "participation": "Remove from team activities. Off-pitch rehab minimum 2 weeks.",
                "medical": "MRI highly recommended to grade structural damage.",
                "coach_notification": "Significant rotation required. Target return in 4-6 weeks.",
                "escalation": "Strict load management until tissue healing is confirmed.",
            }
        else: # 43_plus or legacy
            actions = {
                "participation": "Remove from team training immediately",
                "medical": "URGENT: Refer for specialist assessment — imaging required.",
                "coach_notification": "Long-term absence. Adjust squad depth planning.",
                "escalation": "Full immobilization or surgery consultation may be required.",
            }

        run = PhysioAbsencePredictionRun.objects.create(
            requester=request.user if request.user.is_authenticated else None,
            player_name=player_name,
            age=age,
            position=position,
            injury_type=injury_type,
            context=context,
            previous_same_zone=previous_same_zone,
            recurrence_same_zone=recurrence,
            severity_score=round(severity_score, 4),
            severity_class=severity_class,
            confidence_band=conf,
            absence_days_min=days_min,
            absence_days_max=days_max,
            absence_weeks_label=expected_label,
            immediate_actions=actions,
        )

        similar_payload = {
            "age": age,
            "previous_same_zone": previous_same_zone,
            "recurrence_same_zone": recurrence,
            "training_load_band": load_band,
            "absence_anchor_days": int((days_min + days_max) / 2),
        }
        matches = similar_for_absence(similar_payload, k=3)

        for m in matches:
            case = PhysioHistoricalCase.objects.filter(pk=m.case_id).first()
            if not case:
                continue
            PhysioSimilarityMatch.objects.create(
                function_type="absence_prediction",
                absence_run=run,
                case=case,
                rank=m.rank,
                distance=m.distance,
                match_pct=m.match_pct,
                summary=m.summary,
            )

        run.similar_cases_count = len(matches)
        run.save(update_fields=["similar_cases_count"])

        vals = [m.payload.get("absence_days", 0) for m in matches] or [days_min, days_max]
        
        response_data = {
            "run_id": run.id,
            "absence_prediction": {
                "severity": "Serious" if severity_class == "long" else "Moderate",
                "confidence": conf,
                "days_min": days_min,
                "days_max": days_max,
                "weeks_label": expected_label,
            },
            "immediate_actions": actions,
            "historical_case_matching": {
                "count": len(matches),
                "average_days": round(mean(vals), 1),
                "median_days": sorted(vals)[len(vals) // 2],
                "shortest_days": min(vals),
                "longest_days": max(vals),
                "cases": [
                    {
                        "rank": m.rank,
                        "match_pct": m.match_pct,
                        "summary": m.summary,
                        "absence_days": m.payload.get("absence_days", 0),
                        "profile": m.payload,
                    }
                    for m in matches
                ],
            },
        }

        if predicted_days is not None:
            response_data["predicted_days"] = predicted_days
            response_data["severity_bucket"] = severity_bucket
            response_data["model_type"] = model_type
            response_data["fallback_used"] = False
        else:
            response_data["fallback_used"] = True

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
